"""OneBot v11 反向 WebSocket 服务端传输层。

本模块让适配器监听端口，由 SnowLuma / NapCat 以 OneBot 反向 WebSocket
客户端身份连入。

协议要点：

* 连接建立后，对端通过这条连接主动推送事件（``post_type`` 等）；
* 适配器通过同一条连接发送 ``{"action": ..., "params": ..., "echo": ...}``，
  对端在连接内返回带同名 ``echo`` 的响应；
* 鉴权支持 ``Authorization: Bearer <token>`` 与 ``?access_token=<token>`` 两种
  OneBot v11 标准方式，并可用来源 IP 白名单兜底；
* 对端在握手阶段携带 ``X-Self-ID``，用于识别账号并拒绝不同账号的并发接入；
* 路径支持 ``/onebot/v11/ws/{slot}``：每个 slot 一条独立连接、独立发送锁，
  大消息只阻塞自己那条链路；不带后缀时视为 slot ``0``。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
from typing import TYPE_CHECKING, Any, Callable, Coroutine, Dict, Optional, Set
from uuid import uuid4

from .auth import authorize_request, authorize_self_id, is_ip_allowed, token_matches
from .connection_pool import (
    ConnectionPool,
    SlotConnection,
    normalize_role,
    normalize_slot,
)

if TYPE_CHECKING:  # pragma: no cover - 仅用于类型检查
    from ..config import QQReverseServerConfig
    from ..profile import ProfileState

try:
    from aiohttp import WSCloseCode, WSMsgType, web

    AIOHTTP_AVAILABLE = True
except ImportError:  # pragma: no cover - 运行环境缺少依赖时
    WSCloseCode = None  # type: ignore[assignment]
    WSMsgType = None  # type: ignore[assignment]
    web = None  # type: ignore[assignment]
    AIOHTTP_AVAILABLE = False


_SLOT_PATTERN = re.compile(r"^[0-9A-Za-z_-]{1,32}$")
"""槽位名允许的字符集，避免把奇怪路径当成 slot。"""

_MAX_SLOT_RECLAIM_INTERVAL_SEC = 15.0
"""槽位回收任务的巡检间隔上限。"""


class QQTransportServer:
    """OneBot 反向 WebSocket 服务端。

    对外接口与 :class:`~.base.Transport` 协议保持一致，宿主只装配这一种传输实现。
    """

    def __init__(
        self,
        logger: Any,
        on_connection_opened: Callable[[], Coroutine[Any, Any, None]],
        on_connection_closed: Callable[[], Coroutine[Any, Any, None]],
        on_payload: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        """初始化反向传输层。

        Args:
            logger: 插件日志对象。
            on_connection_opened: 首个连接建立后的异步回调。
            on_connection_closed: 最后一个连接断开后的异步回调。
            on_payload: 收到非 echo 载荷后的异步回调。
        """
        self._logger = logger
        self._on_connection_opened = on_connection_opened
        self._on_connection_closed = on_connection_closed
        self._on_payload = on_payload
        self._config: Optional["QQReverseServerConfig"] = None
        self._profile_state: Optional["ProfileState"] = None
        self._runner: Optional[Any] = None
        self._site: Optional[Any] = None
        self._app: Optional[Any] = None
        self._pool = ConnectionPool()
        self._ws: Optional[Any] = None  # 事件连接；其余 slot 只记录在连接池里
        self._active_self_id: str = ""
        self._background_tasks: Set[asyncio.Task[Any]] = set()
        self._connection_lock = asyncio.Lock()
        self._slot_reaper_task: Optional[asyncio.Task[Any]] = None
        self._connection_active = False
        self._stop_requested = False
        # 连接建立后需先完成画像探测与网关激活，之后注入的事件才会被 Host 接受。
        # 事件先入队、由独立 worker 在就绪后消费，避免阻塞读循环导致 echo 无人接收。
        self._bootstrap_ready = asyncio.Event()
        self._payload_queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()

    @classmethod
    def is_available(cls) -> bool:
        """判断当前环境是否安装了传输层依赖。

        Returns:
            bool: 若已安装 ``aiohttp``，则返回 ``True``。
        """
        return AIOHTTP_AVAILABLE

    def configure(
        self,
        server_config: "QQReverseServerConfig",
        profile_state: Optional["ProfileState"] = None,
    ) -> None:
        """更新反向服务端配置。

        Args:
            server_config: 最新生效的反向服务端配置。
            profile_state: 当前连接的画像容器（保留给上层诊断使用）。
        """
        self._config = server_config
        self._profile_state = profile_state

    async def start(self) -> None:
        """启动反向 WebSocket 监听。

        Raises:
            RuntimeError: 当缺少配置、依赖或鉴权手段时抛出。
        """
        if not self.is_available():
            raise RuntimeError("SnowLuma 反向适配器依赖 aiohttp，但当前环境未安装该依赖")
        if self._config is None:
            raise RuntimeError("SnowLuma 反向适配器尚未配置 [server]")

        config = self._config
        if not config.token and not config.allowed_ips:
            raise RuntimeError(
                "反向服务端未配置 token 且未设置 allowed_ips，拒绝以无鉴权方式监听"
            )

        if self._runner is not None:
            # 配置热更新：先释放旧监听，避免端口占用。
            await self.stop()

        self._stop_requested = False
        listen_path = config.normalized_path().rstrip("/") or config.normalized_path()
        app = web.Application()
        app.router.add_get(listen_path, self._handle_websocket)
        # 带 slot 后缀的连接各自独立；不带后缀的连接按 slot 0 处理。
        app.router.add_get(f"{listen_path}/{{slot}}", self._handle_websocket)
        app.router.add_get("/healthz", self._handle_health)

        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        site = web.TCPSite(runner, config.listen_host, config.listen_port)
        try:
            await site.start()
        except Exception:
            with contextlib.suppress(Exception):
                await runner.cleanup()
            raise

        self._app = app
        self._runner = runner
        self._site = site
        self._start_slot_reaper()
        idle_timeout = float(getattr(config, "slot_idle_timeout_sec", 0.0) or 0.0)
        self._logger.info(
            f"SnowLuma 反向适配器已监听 ws://{config.listen_host}:{config.listen_port}"
            f"{listen_path} 与 {listen_path}/{{slot}}"
            f"（鉴权: {'token' if config.token else '仅 IP 白名单'}"
            f"，slot 空闲回收: {f'{idle_timeout:.0f}s' if idle_timeout > 0 else '关闭'}）"
        )

    async def stop(self) -> None:
        """停止监听、关闭在途连接并清理后台任务。"""
        self._stop_requested = True
        self._stop_slot_reaper()

        for connection in self._pool.connections():
            await self._close_connection(connection, reason="适配器正在停止")
        self._ws = None
        self._active_self_id = ""

        runner = self._runner
        self._runner = None
        self._site = None
        self._app = None
        if runner is not None:
            with contextlib.suppress(Exception):
                await runner.cleanup()

        await self._cancel_background_tasks()
        await self._notify_connection_closed()

    async def call_action(
        self,
        action_name: str,
        params: Dict[str, Any],
        *,
        slot: str = "",
    ) -> Dict[str, Any]:
        """从连接池挑选一条连接发送 OneBot 动作并等待 echo 响应。

        Args:
            action_name: OneBot 动作名称。
            params: 动作参数。
            slot: 可选指定槽位；留空时按配置的选路策略选择。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。

        Raises:
            RuntimeError: 当没有已连接的对端时抛出。
        """

        config = self._config
        if config is None:
            raise RuntimeError("对端未连接")

        connection = self._pool.pick(
            params,
            routing=str(getattr(config, "slot_routing", "sticky") or "sticky"),
            preferred_slot=slot,
            # 查询类动作不参与会话保序，直接挑最空闲的连接，避免排在别人后面。
            ordered=not action_name.startswith(("get_", "can_", "check_")),
        )
        if connection is None:
            raise RuntimeError("对端未连接")

        return await self._call_action_on(connection, action_name, params)

    async def _call_action_on(
        self,
        connection: SlotConnection,
        action_name: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """在指定连接上发送动作，只占用该连接自己的发送锁。"""

        config = self._config
        if config is None or not connection.open:
            raise RuntimeError("对端未连接")

        echo_id = uuid4().hex
        loop = asyncio.get_running_loop()
        response_future: asyncio.Future[Dict[str, Any]] = loop.create_future()
        connection.pending[echo_id] = response_future
        connection.in_flight += 1

        request_payload = {"action": action_name, "params": params, "echo": echo_id}
        try:
            async with connection.send_lock:
                await connection.ws.send_str(json.dumps(request_payload, ensure_ascii=False))
            return await asyncio.wait_for(response_future, timeout=config.action_timeout_sec)
        finally:
            connection.pending.pop(echo_id, None)
            connection.in_flight = max(0, connection.in_flight - 1)
            connection.touch()

    # ------------------------------------------------------------------
    # HTTP / WebSocket 处理
    # ------------------------------------------------------------------

    async def _handle_health(self, request: Any) -> Any:
        """健康检查端点，便于反向代理与容器探活。

        Args:
            request: aiohttp 请求对象。

        Returns:
            aiohttp 响应对象，包含监听与连接状态。
        """
        result: Dict[str, Any] = {
            "ok": True,
            "listening": self._runner is not None,
            "connected": self._pool.has_connection(),
            "slot_count": len(self._pool.connections()),
        }
        config = self._config
        if config is not None and config.token and token_matches(request, config.token):
            result["self_id"] = self._active_self_id
            result["slots"] = [
                {
                    "slot": item.slot,
                    "role": item.role,
                    "self_id": item.self_id,
                    "in_flight": item.in_flight,
                    "idle_seconds": round(item.idle_seconds(), 1),
                }
                for item in self._pool.connections()
            ]
        return web.json_response(result)

    async def _handle_websocket(self, request: Any) -> Any:
        """处理 OneBot 反向 WebSocket 握手与消息循环。

        Args:
            request: aiohttp 请求对象。

        Returns:
            aiohttp 的 WebSocket 响应对象。
        """
        config = self._config
        if config is None:
            return web.Response(status=503, text="adapter not configured")

        allowed, reason = self._authorize(request, config)
        if not allowed:
            self._logger.warning(f"SnowLuma 反向连接被拒绝: {reason}（来源 {request.remote}）")
            return web.Response(status=401, text=reason)

        self_id = str(request.headers.get("X-Self-ID") or "").strip()
        allowed, reason = authorize_self_id(self_id, config)
        if not allowed:
            self._logger.warning(f"SnowLuma 反向连接被拒绝: {reason}（来源 {request.remote}）")
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            await ws.close(
                code=WSCloseCode.POLICY_VIOLATION if WSCloseCode else 1008,
                message=reason.encode("utf-8"),
            )
            return ws

        slot = normalize_slot(request.match_info.get("slot"))
        if not _SLOT_PATTERN.match(slot):
            return web.Response(status=404, text="invalid slot")

        max_slots = int(getattr(config, "max_slots", 8) or 0)
        if max_slots > 0 and self._pool.get(slot) is None and len(self._pool.connections()) >= max_slots:
            self._logger.warning(f"拒绝新连接：槽位数量已达上限 {max_slots}（slot={slot}）")
            return web.Response(status=503, text="too many slots")

        role = normalize_role(request.headers.get("X-Client-Role"))

        ws = web.WebSocketResponse(
            heartbeat=config.heartbeat_interval or None,
            # aiohttp 的回读超时会主动断开空闲连接，反向 WS 必须关闭它，
            # 否则长时间没有 QQ 消息时会误杀健康连接。
            receive_timeout=None,
            max_msg_size=config.max_message_size,
        )
        await ws.prepare(request)

        peer = self._describe_peer(request)
        connection = SlotConnection(slot=slot, ws=ws, self_id=self_id, role=role)

        async with self._connection_lock:
            conflicting = next(
                (
                    item
                    for item in self._pool.connections()
                    if item.self_id and self_id and item.self_id != self_id
                ),
                None,
            )
            if conflicting is not None:
                await ws.close(
                    code=WSCloseCode.POLICY_VIOLATION if WSCloseCode else 1008,
                    message=b"another self_id is already connected",
                )
                self._logger.warning(
                    f"拒绝账号 {self_id} 接入：当前已有账号 {conflicting.self_id} 在线"
                    f"（slot={conflicting.slot}）"
                )
                return ws

            replaced = self._pool.add(connection)
            if replaced is not None:
                # 同槽位重连：释放旧连接，避免响应发往废弃 socket。
                with contextlib.suppress(Exception):
                    await replaced.ws.close(
                        code=WSCloseCode.GOING_AWAY if WSCloseCode else 1001,
                        message=b"replaced by a new connection",
                    )
            carries_events = connection.carries_events
            if carries_events:
                event_peer = self._pool.event_connection(exclude=connection)
                if event_peer is not None:
                    # 事件通道保持唯一：新的事件连接接管旧的，避免同一事件被投递两次。
                    self._logger.info(
                        f"事件连接切换到 slot={slot}，关闭旧的 slot={event_peer.slot}"
                    )
                    with contextlib.suppress(Exception):
                        await event_peer.ws.close(
                            code=WSCloseCode.GOING_AWAY if WSCloseCode else 1001,
                            message=b"event channel moved to another slot",
                        )
                self._ws = ws
                self._active_self_id = self_id

        self._logger.info(
            f"SnowLuma 反向连接已建立: slot={slot} role={role} {peer}"
            f"{f'，X-Self-ID={self_id}' if self_id else ''}"
        )

        worker_task: Optional[asyncio.Task[Any]] = None
        bootstrap_task: Optional[asyncio.Task[Any]] = None
        if carries_events:
            # 新事件连接重置就绪状态与队列，防止上一轮残留事件被误投递。
            self._bootstrap_ready.clear()
            self._payload_queue = asyncio.Queue()
            worker_task = self._create_background_task(
                self._payload_worker(), "reverse_adapter.payload_worker"
            )
            # 连接建立回调会发起 get_version_info 等动作并等待 echo，必须与读循环并发：
            # 若在这里同步 await，读循环尚未启动，echo 永远无人接收，链路会卡到动作超时。
            bootstrap_task = self._create_background_task(
                self._bootstrap_and_mark_ready(), "reverse_adapter.bootstrap"
            )

        disconnect_reason = "对端关闭了连接"
        try:
            async for message in ws:
                if message.type != WSMsgType.TEXT:
                    if message.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR):
                        disconnect_reason = self._describe_terminal_message(ws, message)
                        break
                    continue

                payload = self._parse_json_message(message.data)
                if payload is None:
                    continue

                echo_id = str(payload.get("echo") or "").strip()
                if echo_id:
                    self._resolve_pending_action(connection, echo_id, payload)
                    continue

                if carries_events:
                    self._payload_queue.put_nowait(payload)
                else:
                    self._logger.debug(
                        f"slot={slot} 为发送专用连接，忽略上行事件: "
                        f"{payload.get('post_type', '')}"
                    )
        except asyncio.CancelledError:
            disconnect_reason = "适配器正在停止"
            raise
        except Exception as exc:  # 对端异常断开
            disconnect_reason = f"连接异常: {exc}"
        finally:
            removed = self._pool.remove(connection)
            self._fail_pending_actions(connection, "连接已中断")
            for task in (worker_task, bootstrap_task):
                if task is not None and not task.done():
                    task.cancel()
            async with self._connection_lock:
                event_gone = self._ws is ws
                if event_gone:
                    self._ws = None
                    self._active_self_id = ""
            self._logger.warning(
                f"SnowLuma 反向连接已断开: slot={slot} {peer}，{disconnect_reason}"
            )
            # 被同槽位新连接顶掉时不算整体断连，避免上层把刚建立的链路标记为离线。
            if event_gone and removed:
                await self._notify_connection_closed()

        return ws

    async def _bootstrap_and_mark_ready(self) -> None:
        """执行连接建立回调，并在结束后放开事件派发。

        无论探测成功与否都置位就绪事件，让排队事件按正常路径处理并暴露真实错误，
        而不是静默堆积。
        """

        try:
            await self._notify_connection_opened()
        finally:
            self._bootstrap_ready.set()

    async def _payload_worker(self) -> None:
        """等待网关就绪后串行消费排队事件。"""

        try:
            await self._bootstrap_ready.wait()
        except asyncio.CancelledError:
            raise

        while not self._stop_requested:
            payload = await self._payload_queue.get()
            try:
                await self._on_payload(payload)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._logger.error(f"SnowLuma 反向适配器处理事件失败: {exc}", exc_info=True)
            finally:
                self._payload_queue.task_done()

    @staticmethod
    def _describe_peer(request: Any) -> str:
        """构造用于日志的对端标识（IP:端口）。

        Args:
            request: aiohttp 请求对象。

        Returns:
            str: 对端标识；无法获取端口时只返回 IP。
        """

        remote = str(request.remote or "unknown")
        transport = getattr(request, "transport", None)
        if transport is None:
            return remote

        peername = transport.get_extra_info("peername")
        if isinstance(peername, (tuple, list)) and len(peername) >= 2:
            return f"{remote}:{peername[1]}"
        return remote

    def _authorize(self, request: Any, config: "QQReverseServerConfig") -> tuple[bool, str]:
        """校验来源 IP 与访问令牌。

        Args:
            request: aiohttp 请求对象。
            config: 当前生效的反向服务端配置。

        Returns:
            tuple[bool, str]: 是否放行，以及拒绝原因。
        """
        return authorize_request(request, config)

    @staticmethod
    def _is_ip_allowed(remote: Optional[str], allowed_ips: list[str]) -> bool:
        """判断来源 IP 是否命中白名单。

        Args:
            remote: 对端 IP 字符串。
            allowed_ips: 允许的 IP 或 CIDR 列表；为空表示不限制。

        Returns:
            bool: 命中或未配置白名单时返回 ``True``。
        """
        return is_ip_allowed(remote, allowed_ips)

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _describe_terminal_message(self, ws: Any, message: Any) -> str:
        """描述导致连接结束的终止类消息。

        Args:
            ws: 当前 WebSocket 响应对象。
            message: aiohttp 返回的终止消息。

        Returns:
            str: 汇总后的终止原因描述。
        """
        details = []
        close_code = getattr(ws, "close_code", None)
        if close_code not in (None, 0):
            details.append(f"close_code={close_code}")

        message_data = getattr(message, "data", None)
        if message_data not in (None, "", 0, close_code):
            details.append(f"data={message_data}")

        exception = ws.exception()
        if exception is not None:
            details.append(f"exception={exception}")

        label = "对端关闭了连接" if not details else "连接已结束"
        return f"{label}（{', '.join(str(item) for item in details)}）" if details else label

    def _parse_json_message(self, data: Any) -> Optional[Dict[str, Any]]:
        """解析 WebSocket 文本消息中的 JSON 数据。

        Args:
            data: WebSocket 收到的原始文本数据。

        Returns:
            Optional[Dict[str, Any]]: 成功时返回字典，失败时返回 ``None``。
        """
        try:
            payload = json.loads(str(data))
        except Exception as exc:
            self._logger.warning(f"SnowLuma 反向适配器解析 JSON 载荷失败: {exc}")
            return None

        return payload if isinstance(payload, dict) else None

    def _create_background_task(
        self, coroutine: Coroutine[Any, Any, Any], name: str
    ) -> asyncio.Task[Any]:
        """创建并跟踪后台任务。

        Args:
            coroutine: 待执行的协程对象。
            name: 任务名。

        Returns:
            asyncio.Task[Any]: 已创建的后台任务。
        """
        task = asyncio.create_task(coroutine, name=name)
        self._background_tasks.add(task)
        task.add_done_callback(self._handle_background_task_completion)
        return task

    def _handle_background_task_completion(self, task: asyncio.Task[Any]) -> None:
        """处理后台任务结束后的清理与异常记录。

        Args:
            task: 已结束的后台任务。
        """
        self._background_tasks.discard(task)
        if task.cancelled():
            return

        exception = task.exception()
        if exception is not None:
            self._logger.error(f"SnowLuma 反向适配器后台任务异常: {exception}", exc_info=True)

    async def _cancel_background_tasks(self) -> None:
        """取消所有仍在运行的后台任务。"""
        background_tasks = list(self._background_tasks)
        for task in background_tasks:
            task.cancel()
        if background_tasks:
            with contextlib.suppress(Exception):
                await asyncio.gather(*background_tasks, return_exceptions=True)
        self._background_tasks.clear()

    async def _notify_connection_opened(self) -> None:
        """在连接建立后触发上层回调。"""
        if self._connection_active:
            return

        self._connection_active = True
        try:
            await self._on_connection_opened()
        except Exception as exc:
            self._logger.warning(f"SnowLuma 反向适配器连接建立回调失败: {exc}")

    async def _notify_connection_closed(self) -> None:
        """在连接断开后触发上层回调。"""
        if not self._connection_active:
            return

        self._connection_active = False
        try:
            await self._on_connection_closed()
        except Exception as exc:
            self._logger.warning(f"SnowLuma 反向适配器断连回调失败: {exc}")

    def _resolve_pending_action(
        self,
        connection: SlotConnection,
        echo_id: str,
        payload: Dict[str, Any],
    ) -> None:
        """解析等待中的动作响应。

        Args:
            connection: 收到响应的连接。
            echo_id: 动作请求对应的 echo 标识。
            payload: 对端返回的响应载荷。
        """

        response_future = connection.pending.get(echo_id)
        if response_future is None or response_future.done():
            return
        response_future.set_result(payload)

    def _fail_pending_actions(self, connection: SlotConnection, error_message: str) -> None:
        """让某条连接上所有等待中的动作以异常方式结束。

        Args:
            connection: 目标连接。
            error_message: 写入异常中的错误信息。
        """

        for response_future in list(connection.pending.values()):
            if not response_future.done():
                response_future.set_exception(RuntimeError(error_message))
        connection.pending.clear()

    async def _close_connection(self, connection: SlotConnection, reason: str = "") -> None:
        """关闭一条连接。

        Args:
            connection: 目标连接。
            reason: 写入 close 帧的原因。
        """

        ws = connection.ws
        if ws is None or ws.closed:
            return
        message = reason.encode("utf-8") if reason else None
        with contextlib.suppress(Exception):
            await ws.close(
                code=WSCloseCode.GOING_AWAY if WSCloseCode else 1001,
                message=message,
            )

    def _slot_reap_interval(self) -> float:
        """计算槽位回收任务的巡检间隔。"""

        timeout = float(getattr(self._config, "slot_idle_timeout_sec", 0.0) or 0.0)
        if timeout <= 0:
            return _MAX_SLOT_RECLAIM_INTERVAL_SEC
        return max(1.0, min(_MAX_SLOT_RECLAIM_INTERVAL_SEC, timeout / 4.0))

    def _start_slot_reaper(self) -> None:
        """启动空闲槽位回收任务；空闲阈值为 0 时跳过。"""

        self._stop_slot_reaper()
        timeout = float(getattr(self._config, "slot_idle_timeout_sec", 0.0) or 0.0)
        if timeout <= 0:
            return
        self._slot_reaper_task = self._create_background_task(
            self._slot_reaper_loop(), "reverse_adapter.slot_reaper"
        )

    def _stop_slot_reaper(self) -> None:
        """停止空闲槽位回收任务。"""

        task = self._slot_reaper_task
        self._slot_reaper_task = None
        if task is not None and not task.done():
            task.cancel()

    async def _slot_reaper_loop(self) -> None:
        """周期性关闭长期空闲的非事件槽位。"""

        while not self._stop_requested:
            await asyncio.sleep(self._slot_reap_interval())
            config = self._config
            if config is None:
                continue
            timeout = float(getattr(config, "slot_idle_timeout_sec", 0.0) or 0.0)
            if timeout <= 0:
                continue
            event_connection = self._pool.event_connection()
            protected = [event_connection.slot] if event_connection is not None else []
            for connection in self._pool.idle_connections(timeout, protected_slots=protected):
                self._logger.info(
                    f"回收空闲槽位 slot={connection.slot}"
                    f"（已空闲 {connection.idle_seconds():.0f}s）"
                )
                await self._close_connection(connection, reason="idle slot recycled")

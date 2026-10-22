"""反向 WebSocket 传输层自测（不依赖 maibot_sdk）。

模拟 SnowLuma 以 OneBot v11 反向 WebSocket 客户端身份连入适配器，验证：

1. token 鉴权拒绝；
2. 对端主动推送的事件能到达 on_payload；
3. 适配器发起的 action 能在同一条连接上收到 echo 响应；
4. 空闲超过 aiohttp 默认回读超时（10s）后连接仍然存活；
5. 不同 X-Self-ID 的并发连接被拒，同账号重连替换旧连接；
6. 无连接时调用 action 报错。

运行：``python3 tests/test_transport_server.py``
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import aiohttp

ROOT = Path(__file__).resolve().parent.parent
PATH = "/onebot/v11/ws"
PORT = 16727
TOKEN = "test-token"
URL = f"ws://127.0.0.1:{PORT}{PATH}"


def load_transport_module():
    """按文件路径加载 transport_server 模块。

    Returns:
        module: 已加载的模块对象。
    """

    spec = importlib.util.spec_from_file_location(
        "snowluma_reverse_transport", ROOT / "transport_server.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_config() -> SimpleNamespace:
    """构造与 QQReverseServerConfig 字段一致的测试配置。

    Returns:
        SimpleNamespace: 供传输层读取的配置对象。
    """

    return SimpleNamespace(
        listen_host="127.0.0.1",
        listen_port=PORT,
        listen_path=PATH,
        token=TOKEN,
        allowed_ips=[],
        expect_self_id="",
        heartbeat_interval=30.0,
        action_timeout_sec=5.0,
        max_message_size=16 * 1024 * 1024,
        connection_id="",
        normalized_path=lambda: PATH,
    )


class Recorder:
    """记录传输层回调，便于断言。"""

    def __init__(self) -> None:
        """初始化记录器。"""

        self.opened = 0
        self.closed = 0
        self.payloads: list[dict] = []

    async def on_connection_opened(self) -> None:
        """记录连接建立。"""

        self.opened += 1

    async def on_connection_closed(self) -> None:
        """记录连接断开。"""

        self.closed += 1

    async def on_payload(self, payload: dict) -> None:
        """记录非 echo 载荷。"""

        self.payloads.append(payload)


async def connect(self_id: str, token: str = TOKEN):
    """建立一条模拟 SnowLuma 的连接。

    Args:
        self_id: 握手头 X-Self-ID。
        token: 访问令牌。

    Returns:
        tuple[aiohttp.ClientSession, aiohttp.ClientWebSocketResponse]: 会话与连接。
    """

    session = aiohttp.ClientSession()
    try:
        ws = await session.ws_connect(
            URL,
            headers={"X-Self-ID": self_id, "Authorization": f"Bearer {token}"},
        )
    except Exception:
        await session.close()
        raise
    return session, ws


async def send_group_message(ws, text: str = "hello") -> None:
    """推送一条群消息事件。

    Args:
        ws: 客户端连接。
        text: 消息文本。
    """

    await ws.send_str(
        json.dumps(
            {
                "post_type": "message",
                "message_type": "group",
                "group_id": 123456,
                "user_id": 654321,
                "raw_message": text,
                "message_id": 1,
                "self_id": 10001,
            },
            ensure_ascii=False,
        )
    )


async def answer_actions(ws, stop: asyncio.Event) -> None:
    """应答服务端下发的 get_group_info action。

    Args:
        ws: 客户端连接。
        stop: 收到请求后置位，用于结束等待。
    """

    async for message in ws:
        if message.type != aiohttp.WSMsgType.TEXT:
            return
        payload = json.loads(message.data)
        if payload.get("action") == "get_group_info":
            await ws.send_str(
                json.dumps(
                    {
                        "status": "ok",
                        "retcode": 0,
                        "data": {"group_id": 123456, "group_name": "测试群"},
                        "echo": payload["echo"],
                    },
                    ensure_ascii=False,
                )
            )
            stop.set()
            return


async def main() -> int:
    """执行全部断言。

    Returns:
        int: 全部通过返回 0，否则返回 1。
    """

    module = load_transport_module()
    QQTransportServer = module.QQTransportServer

    recorder = Recorder()
    server = QQTransportServer(
        logger=logging.getLogger("test"),
        on_connection_opened=recorder.on_connection_opened,
        on_connection_closed=recorder.on_connection_closed,
        on_payload=recorder.on_payload,
    )
    server.configure(make_config())
    await server.start()

    failures: list[str] = []

    # 1) 错误 token 必须被拒。
    try:
        session, ws = await connect("10001", token="wrong")
        await ws.close()
        await session.close()
        failures.append("错误 token 竟然握手成功")
    except aiohttp.WSServerHandshakeError as exc:
        if exc.status != 401:
            failures.append(f"错误 token 返回 {exc.status}，预期 401")

    # 2) 正常链路：事件上行 + action 下行。
    session_a, ws_a = await connect("10001")
    await send_group_message(ws_a)
    for _ in range(50):
        if recorder.payloads:
            break
        await asyncio.sleep(0.1)
    if not recorder.payloads:
        failures.append("没有收到对端推送的事件")

    action_done = asyncio.Event()
    action_task = asyncio.create_task(answer_actions(ws_a, action_done))
    try:
        response = await server.call_action("get_group_info", {"group_id": 123456})
        if response.get("data", {}).get("group_name") != "测试群":
            failures.append(f"action 响应异常: {response}")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"call_action 失败: {exc!r}")
    finally:
        action_task.cancel()

    # 3) 空闲 12 秒（超过 aiohttp 默认 10 秒回读超时）后连接仍须存活。
    await asyncio.sleep(12)
    if ws_a.closed:
        failures.append("空闲 12 秒后连接被断开（receive_timeout 未关闭）")

    # 4) 不同 X-Self-ID 的并发连接必须被拒（1008）。
    try:
        session_b, ws_b = await connect("20002")
        message = await ws_b.receive(timeout=3)
        if ws_b.close_code != 1008:
            failures.append(
                f"不同账号并发未被拒: type={message.type}, close_code={ws_b.close_code}"
            )
        await session_b.close()
    except aiohttp.WSServerHandshakeError:
        pass

    # 5) 同账号重连替换旧连接。
    session_c, ws_c = await connect("10001")
    replaced_message = await ws_a.receive(timeout=5)
    if replaced_message.type != aiohttp.WSMsgType.CLOSE:
        failures.append(f"同账号重连未替换旧连接: type={replaced_message.type}")
    await send_group_message(ws_c, "after-reconnect")
    await asyncio.sleep(0.3)
    if not any(item.get("raw_message") == "after-reconnect" for item in recorder.payloads):
        failures.append("新连接的事件没有送达 on_payload")

    await ws_c.close()
    await session_c.close()
    await ws_a.close()
    await session_a.close()

    # 6) 全部断开后调用 action 必须报错。
    await asyncio.sleep(0.5)
    try:
        await server.call_action("get_login_info", {})
        failures.append("断线后 call_action 未报错")
    except RuntimeError:
        pass

    await server.stop()

    print(
        json.dumps(
            {
                "failures": failures,
                "opened": recorder.opened,
                "closed": recorder.closed,
                "payload_count": len(recorder.payloads),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

"""SnowLuma 适配器（统一 QQ 连接器）插件。

以 SnowLuma 适配器的模块结构为基底，合并 SnowLuma 适配器的特性：
1. 作为 OneBot v11 反向 WebSocket 服务端监听端口，等 SnowLuma / NapCat 反向连入，
   连接后通过 ``get_version_info`` 自动判定对端并应用对应能力画像。
2. 将入站消息、通知事件与元事件转换为 Host 侧结构。
3. 将 Host 出站消息转换为按画像定制的 OneBot 动作序列并发送。
4. 通过公开 API 暴露 QQ 平台专属查询与管理动作（含 SnowLuma 专属 QZone 组）。
5. 提供可配置开关的 LLM 工具：主动私聊、戳一戳、消息撤回、智能禁言、表情表态与消息转发（附活跃聊天流查询）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar, Dict, List, Mapping, Optional, cast

from maibot_sdk import MaiBotPlugin, PluginConfigBase

from .apis import (
    QQAccountApiMixin,
    QQFileApiMixin,
    QQGroupApiMixin,
    QQMessageApiMixin,
    QQQzoneApiMixin,
    QQSystemApiMixin,
)
from .config import QQPluginSettings
from .constants import SNOWLUMA_GATEWAY_NAME
from .gateway import QQMessageGatewayMixin
from .tools import QQLlmToolsMixin
from .debug import AdaDebugLogger
from .media import face_vision_worker
from .media.face_vision_store import STORE
from .media.face_vision_worker import FaceVisionWorker
from .profile import PROFILE_BY_TYPE, ClientProfile, ProfileState
from .runtime import QQEventRouter, QQRuntimeBuilder, QQRuntimeBundle
from .services import QQActionService, QQQueryService


class SnowLumaAdapterPlugin(
    QQLlmToolsMixin,
    QQMessageGatewayMixin,
    QQAccountApiMixin,
    QQFileApiMixin,
    QQGroupApiMixin,
    QQMessageApiMixin,
    QQQzoneApiMixin,
    QQSystemApiMixin,
    MaiBotPlugin,
):
    """SnowLuma / SnowLuma / NapCat 统一消息网关与 QQ 能力插件。"""

    config_model: ClassVar[type[PluginConfigBase] | None] = QQPluginSettings

    def __init__(self) -> None:
        """初始化适配器插件实例。"""
        super().__init__()
        self._action_service: Optional[QQActionService] = None
        self._query_service: Optional[QQQueryService] = None
        self._event_router: Optional[QQEventRouter] = None
        self._runtime_bundle: Optional[QQRuntimeBundle] = None
        self._debug_logger: Optional[AdaDebugLogger] = None

    def get_components(self) -> List[Dict[str, Any]]:
        """收集组件，并为 NapCat API 注册同名 SnowLuma 别名。"""
        components = super().get_components()
        aliases: List[Dict[str, Any]] = []
        for component in components:
            if component["type"] != "API" or not component["name"].startswith("adapter.napcat."):
                continue
            # 保留原处理器和完整元数据，让两个前缀共享参数、返回值及能力校验。
            aliases.append(
                {
                    **component,
                    "name": "adapter.snowluma." + component["name"].removeprefix("adapter.napcat."),
                    "metadata": dict(component["metadata"]),
                }
            )
        return components + aliases

    async def on_load(self) -> None:
        """在插件加载时根据配置决定是否启动连接。"""
        await self._sync_tool_components_state()
        await self._restart_connection_if_needed()
        await self._start_face_vision()

    async def on_unload(self) -> None:
        """在插件卸载时关闭连接。"""
        await face_vision_worker.stop()
        await self._stop_connection()

    async def on_config_update(self, scope: str, config_data: Dict[str, Any], version: str) -> None:
        """在配置更新后热重载反向监听。

        Args:
            scope: 配置变更范围。
            config_data: 最新的配置数据。
            version: 配置版本号。
        """
        if scope != "self":
            return

        self.set_plugin_config(config_data)
        if version:
            self.ctx.logger.debug(f"适配器收到配置更新通知: {version}")
        await self._sync_face_vision_config()
        await self._sync_tool_components_state()
        await self._restart_connection_if_needed()

    @staticmethod
    def _is_action_response_ok(response: Mapping[str, Any]) -> bool:
        """判定动作响应是否成功。

        仅受理的异步动作不算发送成功，必须是完成状态且无错误码。

        Args:
            response: 对端返回的原始响应字典。

        Returns:
            bool: 若响应表示成功则返回 ``True``。
        """
        status = str(response.get("status") or "").strip().lower()
        return status == "ok" and response.get("retcode", 0) == 0

    async def _start_face_vision(self) -> None:
        """按配置启动运行时表情补描述 worker；失败只告警，绝不影响消息收发。"""
        config = getattr(self.config, "face_vision", None)
        if config is None:
            return
        try:
            data_dir = Path(str(self.ctx.paths.data_dir))
            STORE.attach_overlay(data_dir)
            STORE.reload()
            worker = FaceVisionWorker(
                STORE,
                data_dir,
                self.ctx.logger,
                enabled=config.enabled,
                desc_max_chars=config.desc_max_chars,
                max_attempts=config.max_attempts,
                timeout_s=config.timeout_s,
                index_refresh_hours=config.index_refresh_hours,
                model_config_path=config.model_config_path,
            )
            await face_vision_worker.start(worker)
        except Exception as error:  # noqa: BLE001 - 补描述属于增强能力，不能拖垮适配器
            self.ctx.logger.warning(f"[表情描述] 运行时补描述启动失败: {error}")

    async def _sync_face_vision_config(self) -> None:
        """配置热更新：worker 已存在就改参数，不存在就按新配置启动。"""
        config = getattr(self.config, "face_vision", None)
        if config is None:
            return
        worker = face_vision_worker.WORKER
        if worker is None:
            await self._start_face_vision()
            return
        worker.reconfigure(
            enabled=config.enabled,
            desc_max_chars=config.desc_max_chars,
            max_attempts=config.max_attempts,
            timeout_s=config.timeout_s,
            index_refresh_hours=config.index_refresh_hours,
            model_config_path=config.model_config_path,
        )
        STORE.reload()
        await worker.start()

    def _ensure_runtime_components(self) -> None:
        """确保运行时依赖对象已经完成初始化。"""
        if self._debug_logger is None:
            self._debug_logger = AdaDebugLogger(self.ctx.logger, self._load_settings)

        if self._event_router is None:
            self._event_router = QQEventRouter(
                gateway_capability=self.ctx.gateway,
                logger=self.ctx.logger,
                gateway_name=SNOWLUMA_GATEWAY_NAME,
                load_settings=self._load_settings,
            )

        if self._runtime_bundle is None:
            settings = self._load_settings()
            profile_state = ProfileState(self._resolve_initial_profile(settings))
            runtime_builder = QQRuntimeBuilder(
                gateway_capability=self.ctx.gateway,
                logger=self.ctx.logger,
                gateway_name=SNOWLUMA_GATEWAY_NAME,
            )
            self._runtime_bundle = runtime_builder.build(
                on_connection_opened=self._event_router.bootstrap_adapter_runtime_state,
                on_connection_closed=self._event_router.handle_transport_disconnected,
                on_payload=self._event_router.handle_transport_payload,
                on_natural_lift=self._event_router.emit_natural_lift_notice,
                on_heartbeat_timeout=self._event_router.handle_heartbeat_timeout,
                profile_state=profile_state,
                load_settings=self._load_settings,
            )
            self._runtime_bundle.transport.configure(settings.server, profile_state)
            self._event_router.bind_runtime(self._runtime_bundle)
            self._bind_runtime_aliases(self._runtime_bundle)

    @staticmethod
    def _resolve_initial_profile(settings: QQPluginSettings) -> ClientProfile:
        """根据配置声明解析连接建立前的初始画像。

        auto 模式下探测尚未完成，先以 画像占位（探测完成后由路由器写回）。

        Args:
            settings: 当前生效的插件配置。

        Returns:
            ClientProfile: 初始画像。
        """
        declared_type = settings.plugin.client_type
        return PROFILE_BY_TYPE.get(declared_type, PROFILE_BY_TYPE["napcat"])

    async def _sync_tool_components_state(self) -> None:
        """按配置同步全部 LLM 工具组件的启停状态。"""

        settings = self._load_settings()
        abilities = settings.chat_abilities
        tool_states = (
            ("open_private_chat", abilities.enable_private_chat_tool),
            ("get_qq_by_msg_id", abilities.enable_private_chat_tool),
            ("send_poke", abilities.enable_poke_tool),
            ("recall_message", abilities.enable_recall_tool),
            ("mute", abilities.enable_mute_tool),
            ("react_emoji", abilities.enable_emoji_like_tool),
            ("list_chat_streams", abilities.enable_forward_tool),
            ("forward_messages", abilities.enable_forward_tool),
        )
        try:
            for tool_name, enabled in tool_states:
                if enabled:
                    result = await self.ctx.component.enable_component(tool_name, "TOOL")
                else:
                    result = await self.ctx.component.disable_component(tool_name, "TOOL")
                if isinstance(result, Mapping) and not bool(result.get("success", False)):
                    self.ctx.logger.warning(
                        f"同步工具启停状态失败: tool={tool_name} "
                        f"error={result.get('error') or result}"
                    )
        except Exception as exc:
            self.ctx.logger.warning(f"同步工具启停状态失败: {exc}")

    def _bind_runtime_aliases(self, runtime_bundle: QQRuntimeBundle) -> None:
        """同步运行时组件到插件级别的快捷引用。

        Args:
            runtime_bundle: 已初始化的运行时组件集合。
        """
        self._action_service = runtime_bundle.action_service
        self._query_service = runtime_bundle.query_service

    def _load_settings(self) -> QQPluginSettings:
        """返回当前生效的插件配置。

        Returns:
            QQPluginSettings: 当前生效的插件配置。
        """
        return cast(QQPluginSettings, self.config)

    async def _restart_connection_if_needed(self) -> None:
        """按配置重启反向监听。"""
        settings = self._load_settings()
        self._ensure_runtime_components()
        runtime_bundle = self._require_runtime_bundle()

        await self._stop_connection()
        if not settings.should_connect():
            self.ctx.logger.info("适配器保持空闲状态，因为插件或配置未启用")
            return
        if not settings.validate_runtime_config(self.ctx.logger):
            return
        if not runtime_bundle.transport.is_available():
            self.ctx.logger.error("适配器依赖 aiohttp，但当前环境未安装该依赖")
            return

        runtime_bundle.regex_filter.reload_patterns(settings.filters.regex_filter_patterns)
        if settings.filters.regex_filter_enabled and settings.filters.regex_filter_patterns:
            self.ctx.logger.info(
                f"正则消息过滤已启用: 模式={settings.filters.regex_filter_mode}，"
                f"规则数={len(settings.filters.regex_filter_patterns)}"
            )
        if not settings.notice.enabled:
            self.ctx.logger.info("通知事件转发已整体关闭：所有通知都不会传入 Host")

        runtime_bundle.transport.configure(settings.server, runtime_bundle.profile_state)
        await runtime_bundle.transport.start()

    async def _stop_connection(self) -> None:
        """停止当前连接并清理运行时缓存。"""
        runtime_bundle = self._runtime_bundle
        if runtime_bundle is None:
            return

        await runtime_bundle.transport.stop()
        if self._event_router is not None:
            self._event_router.reset_caches()

    def _require_runtime_bundle(self) -> QQRuntimeBundle:
        """返回当前已初始化的运行时组件集合。

        Returns:
            QQRuntimeBundle: 当前运行时组件集合。

        Raises:
            RuntimeError: 当运行时尚未初始化时抛出。
        """
        self._ensure_runtime_components()
        runtime_bundle = self._runtime_bundle
        if runtime_bundle is None:
            raise RuntimeError("适配器运行时尚未初始化")
        return runtime_bundle


def create_plugin() -> SnowLumaAdapterPlugin:
    """创建插件实例。

    Returns:
        SnowLumaAdapterPlugin: SnowLuma 适配器插件实例。
    """
    return SnowLumaAdapterPlugin()

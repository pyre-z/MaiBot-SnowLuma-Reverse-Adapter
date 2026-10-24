"""Top-level settings, migration allowlist, and runtime validation."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, Dict

from maibot_sdk import Field, PluginConfigBase
from pydantic import model_validator

from .base import _normalize_string, SUPPORTED_CONFIG_VERSION
from .sections import (
    QQChatAbilitiesConfig, QQDebugConfig, QQFaceVisionConfig, QQFilterConfig, QQMuteConfig,
    QQNoticeConfig, QQPluginOptions, QQReverseServerConfig,
)

LOGGER = logging.getLogger("snowluma_adapter.config")


def _as_mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}

class QQPluginSettings(PluginConfigBase):
    """SnowLuma 反向适配器（OneBot v11 反向 WebSocket 服务端）完整配置。"""

    plugin: QQPluginOptions = Field(default_factory=QQPluginOptions)
    chat_abilities: QQChatAbilitiesConfig = Field(default_factory=QQChatAbilitiesConfig)
    server: QQReverseServerConfig = Field(default_factory=QQReverseServerConfig)
    notice: QQNoticeConfig = Field(default_factory=QQNoticeConfig)
    filters: QQFilterConfig = Field(default_factory=QQFilterConfig)
    debug: QQDebugConfig = Field(default_factory=QQDebugConfig)
    mute: QQMuteConfig = Field(default_factory=QQMuteConfig)
    face_vision: QQFaceVisionConfig = Field(default_factory=QQFaceVisionConfig)

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_config(cls, raw_config: Any) -> Dict[str, Any]:
        """将旧版 SnowLuma / 旧版 NapCat 旧配置结构迁移为当前配置模型。

        旧版的 ``[client]`` 正向连接段已随正向 WebSocket 客户端一并移除，这里只保留其中的
        ``client_type``（对端画像声明），其余连接参数直接丢弃。

        Args:
            raw_config: Runner 注入的原始配置内容。

        Returns:
            Dict[str, Any]: 适配到当前配置模型后的字典结构。
        """

        raw_mapping = _as_mapping(raw_config)
        plugin_section = _as_mapping(raw_mapping.get("plugin"))
        debug_section = _as_mapping(raw_mapping.get("debug"))
        chat_abilities_section = _as_mapping(raw_mapping.get("chat_abilities"))
        # 工具开关从插件设置移到独立分类 [chat_abilities]。
        # SDK 会在校验前用默认值补齐 [chat_abilities]（全 false），因此 [plugin] 中
        # 残留的旧字段值必须无条件搬迁，否则用户的开关状态会被默认值吞掉。
        for field_name in QQChatAbilitiesConfig.model_fields:
            if field_name in plugin_section:
                chat_abilities_section[field_name] = plugin_section.pop(field_name)
        # 调试项从插件设置移到独立分类；保留旧配置的显式值，新分类的值优先。
        for field_name in QQDebugConfig.model_fields:
            if field_name in plugin_section:
                legacy_value = plugin_section.pop(field_name)
                if field_name not in debug_section:
                    debug_section[field_name] = legacy_value
        chat_section = _as_mapping(raw_mapping.get("chat"))
        filters_section = _as_mapping(raw_mapping.get("filters"))
        # 自身消息过滤同样归入调试分类，保留旧配置的显式选择。
        if "ignore_self_message" in filters_section:
            legacy_ignore_self = filters_section.pop("ignore_self_message")
            if "ignore_self_message" not in debug_section:
                debug_section["ignore_self_message"] = legacy_ignore_self
        notice_section = _as_mapping(raw_mapping.get("notice"))
        if "ban_qq_bot" not in filters_section and "ban_qq_bot" in chat_section:
            filters_section["ban_qq_bot"] = chat_section["ban_qq_bot"]
        mute_section = _as_mapping(raw_mapping.get("mute"))
        server_section = _as_mapping(raw_mapping.get("server"))

        # 正向模式已移除：只为 client_type 做迁移，其它 [client] 连接参数与旧版连接段一律丢弃。
        client_section = _as_mapping(raw_mapping.get("client"))
        legacy_client_sections = [
            name for name in ("luma_client", "napcat_server", "connection")
            if _as_mapping(raw_mapping.get(name))
        ]
        if client_section or legacy_client_sections:
            LOGGER.warning(
                "SnowLuma 适配器已移除正向 WebSocket 客户端，[client] 配置段不再生效；"
                "仅迁移其中的 client_type 到 [plugin]，如需连接请让对端反向连入 [server]"
            )
        legacy_client_type = _normalize_string(client_section.get("client_type"))
        if legacy_client_type and not _normalize_string(plugin_section.get("client_type")):
            plugin_section["client_type"] = legacy_client_type
        # 旧配置携带历史版本号时会触发版本校验失败；迁移时统一改写为当前版本。
        if _normalize_string(plugin_section.get("config_version")) not in {"", SUPPORTED_CONFIG_VERSION}:
            plugin_section["config_version"] = SUPPORTED_CONFIG_VERSION

        return {
            "chat_abilities": chat_abilities_section,
            "face_vision": _as_mapping(raw_mapping.get("face_vision")),
            "debug": debug_section,
            "filters": filters_section,
            "mute": mute_section,
            "notice": notice_section,
            "plugin": plugin_section,
            "server": server_section,
        }

    @classmethod
    def from_mapping(cls, raw_config: Mapping[str, Any], logger: Any) -> "QQPluginSettings":
        """从 Runner 注入的原始配置字典解析插件配置。

        Args:
            raw_config: Runner 注入的原始配置内容。
            logger: 兼容旧调用签名保留的日志对象，当前不直接使用。

        Returns:
            QQPluginSettings: 规范化后的插件配置模型。
        """

        del logger
        return cls.model_validate(dict(raw_config))

    def should_connect(self) -> bool:
        """判断当前配置下是否应当启动监听。

        Returns:
            bool: 若插件已启用，则返回 ``True``。
        """

        return self.plugin.should_connect()

    def validate_runtime_config(self, logger: Any) -> bool:
        """校验当前配置是否满足启动反向监听的前提条件。

        Args:
            logger: 插件日志对象。

        Returns:
            bool: 若配置满足启动监听的前提条件，则返回 ``True``。
        """

        config_version = self.plugin.config_version
        if not config_version:
            logger.error(f"适配器配置缺少 plugin.config_version，当前插件要求版本 {SUPPORTED_CONFIG_VERSION}")
            return False

        if config_version != SUPPORTED_CONFIG_VERSION:
            logger.error(
                f"适配器配置版本不兼容: 当前为 {config_version}，当前插件要求 {SUPPORTED_CONFIG_VERSION}"
            )
            return False

        server_config = self.server
        if not server_config.listen_host:
            logger.warning("适配器已启用，但 server.listen_host 为空")
            return False

        if server_config.listen_port <= 0:
            logger.warning("适配器已启用，但 server.listen_port 不是正整数")
            return False

        if not server_config.token and not server_config.allowed_ips:
            logger.error(
                "反向服务端既未配置 server.token，也未配置 server.allowed_ips；"
                "拒绝以无鉴权方式监听，请至少设置其中一项"
            )
            return False

        return True

"""Top-level settings, migration allowlist, and runtime validation."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, Dict, List

from maibot_sdk import Field, PluginConfigBase
from pydantic import model_validator

from .base import _normalize_string, SUPPORTED_CONFIG_VERSION
from .sections import (
    QQChatAbilitiesConfig, QQDebugConfig, QQFilterConfig, QQMuteConfig, QQNoticeConfig,
    QQPluginOptions, QQReverseServerConfig, QQServerConfig,
)
from ..constants import DEFAULT_CLIENT_PORT
LOGGER = logging.getLogger("snowluma_adapter.config")

LOGGER = logging.getLogger("snowluma_adapter.config")


def _as_mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}

class QQPluginSettings(PluginConfigBase):
    """SnowLuma 适配器（统一 QQ 连接器）完整配置。"""

    plugin: QQPluginOptions = Field(default_factory=QQPluginOptions)
    chat_abilities: QQChatAbilitiesConfig = Field(default_factory=QQChatAbilitiesConfig)
    client: QQServerConfig = Field(default_factory=QQServerConfig)
    server: QQReverseServerConfig = Field(default_factory=QQReverseServerConfig)
    notice: QQNoticeConfig = Field(default_factory=QQNoticeConfig)
    filters: QQFilterConfig = Field(default_factory=QQFilterConfig)
    debug: QQDebugConfig = Field(default_factory=QQDebugConfig)
    mute: QQMuteConfig = Field(default_factory=QQMuteConfig)

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_config(cls, raw_config: Any) -> Dict[str, Any]:
        """将旧版 SnowLuma / 旧版 NapCat 旧配置结构迁移为当前配置模型。

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

        client_section = _as_mapping(raw_mapping.get("client"))
        legacy_sources: List[tuple[str, Mapping[str, Any]]] = []
        luma_section = _as_mapping(raw_mapping.get("luma_client"))
        napcat_section = _as_mapping(raw_mapping.get("napcat_server"))
        legacy_connection_section = _as_mapping(raw_mapping.get("connection"))
        if luma_section:
            legacy_sources.append(("luma_client", luma_section))
        if napcat_section:
            legacy_sources.append(("napcat_server", napcat_section))
        if legacy_connection_section:
            legacy_sources.append(("connection", legacy_connection_section))

        if legacy_sources:
            source_name, source_section = legacy_sources[0]
            LOGGER.warning(f"SnowLuma 适配器检测到旧版 [{source_name}] 配置段，已自动迁移到 [client]")
            # Runner/SDK 在校验前会用默认值补齐缺失的配置段，[client] 因此几乎总是非空，
            # 不能再用「[client] 为空」判断是否需要迁移，否则旧配置里的 token 等字段会被
            # 默认值覆盖后永久丢失。这里改为逐字段合并：仅当 [client] 中该字段缺失或为空
            # 时才用旧配置的值填充，已显式设置的用户值优先。
            known_client_keys = set(QQServerConfig.model_fields)
            migrated_client_section = dict(client_section)
            for legacy_key, legacy_value in source_section.items():
                if legacy_key not in known_client_keys:
                    continue
                # SDK 补齐的默认端口也会被视为非空；旧端口应优先于这个默认值。
                if legacy_key == "port" and migrated_client_section.get("port") == DEFAULT_CLIENT_PORT:
                    migrated_client_section["port"] = legacy_value
                    continue
                if _normalize_string(migrated_client_section.get(legacy_key)):
                    continue
                migrated_client_section[legacy_key] = legacy_value
            client_section = migrated_client_section
            # 旧 SnowLuma 配置使用 server 字段；旧 NapCat 配置使用 host 字段，统一映射为 server。
            legacy_host = _normalize_string(client_section.get("host"))
            if legacy_host and not _normalize_string(client_section.get("server")):
                client_section["server"] = legacy_host
            legacy_access_token = _normalize_string(client_section.get("access_token"))
            if legacy_access_token and not _normalize_string(client_section.get("token")):
                client_section["token"] = legacy_access_token

        # 旧配置携带历史版本号时会触发版本校验失败；迁移时统一改写为当前版本。
        if _normalize_string(plugin_section.get("config_version")) not in {"", SUPPORTED_CONFIG_VERSION}:
            plugin_section["config_version"] = SUPPORTED_CONFIG_VERSION

        return {
            "chat_abilities": chat_abilities_section,
            "client": client_section,
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
        """判断当前配置下是否应当启动连接。

        Returns:
            bool: 若插件连接已启用，则返回 ``True``。
        """

        return self.plugin.should_connect()

    def transport_config(self) -> QQServerConfig | QQReverseServerConfig:
        """按 ``transport_mode`` 返回当前生效的传输配置。

        Returns:
            QQServerConfig | QQReverseServerConfig: 正向或反向传输配置。
        """

        if self.plugin.transport_mode == "server":
            return self.server
        return self.client

    def validate_runtime_config(self, logger: Any) -> bool:
        """校验当前配置是否满足启动连接的前提条件。

        Args:
            logger: 插件日志对象。

        Returns:
            bool: 若配置满足启动连接的前提条件，则返回 ``True``。
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

        if self.plugin.transport_mode == "server":
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

        if not self.client.server:
            logger.warning("适配器已启用，但 client.server 为空")
            return False

        if self.client.port <= 0:
            logger.warning("适配器已启用，但 client.port 不是正整数")
            return False

        return True

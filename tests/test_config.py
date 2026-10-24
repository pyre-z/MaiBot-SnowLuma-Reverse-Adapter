"""配置模型回归测试。"""

import logging

import pytest

pytest.importorskip("maibot_sdk")

from snowluma_reverse.config import QQPluginSettings, QQReverseServerConfig


def test_only_reverse_server_transport_remains():
    """正向客户端移除后，配置只剩反向服务端一段，且不再有 transport_mode。"""
    settings = QQPluginSettings.model_validate({})
    assert isinstance(settings.server, QQReverseServerConfig)
    assert not hasattr(settings, "client")
    assert not hasattr(settings.plugin, "transport_mode")


def test_server_runtime_validation_requires_auth_and_valid_listener():
    settings = QQPluginSettings.model_validate({"plugin": {"enabled": True}})
    assert not settings.validate_runtime_config(logging.getLogger("test"))
    settings.server.token = "token"
    settings.server.listen_host = ""
    assert not settings.validate_runtime_config(logging.getLogger("test"))
    settings.server.listen_host = "127.0.0.1"
    settings.server.listen_port = 0
    assert not settings.validate_runtime_config(logging.getLogger("test"))
    settings.server.listen_port = 6727
    assert settings.validate_runtime_config(logging.getLogger("test"))


def test_path_normalization():
    config = QQReverseServerConfig.model_validate({"listen_path": "onebot/v11/ws"})
    assert config.normalized_path() == "/onebot/v11/ws"


def test_legacy_migration_preserves_server_section():
    result = QQPluginSettings._migrate_legacy_config({"server": {"token": "old-token"}})
    assert result["server"]["token"] == "old-token"


def test_legacy_client_section_only_migrates_client_type():
    """旧 [client] 段只迁移对端类型，连接参数一律丢弃。"""
    result = QQPluginSettings._migrate_legacy_config(
        {
            "plugin": {},
            "client": {
                "client_type": "snowluma",
                "server": "10.0.0.2",
                "port": 3001,
                "token": "legacy-token",
                "reconnect_delay_sec": 5.0,
            },
        }
    )
    assert result["plugin"]["client_type"] == "snowluma"
    assert "client" not in result


def test_hot_update_invalid_config_does_not_crash():
    """配置热更新模型校验失败时应抛出可捕获的 ValueError，而不是破坏插件状态。"""
    from snowluma_reverse.config import QQPluginSettings as Settings

    with pytest.raises(ValueError):
        Settings.model_validate({"plugin": {"qq_face_parse_mode": "bogus"}})
    valid = Settings.model_validate({})
    assert valid.server.listen_port == 6727

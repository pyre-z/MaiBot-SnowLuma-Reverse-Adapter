"""配置模型回归测试。"""

import logging

import pytest

pytest.importorskip("maibot_sdk")

from snowluma_reverse.config import QQPluginSettings, QQReverseServerConfig, QQServerConfig


def test_transport_config_selects_mode():
    client = QQPluginSettings.model_validate({"plugin": {"transport_mode": "client"}})
    server = QQPluginSettings.model_validate({"plugin": {"transport_mode": "server"}})
    assert isinstance(client.transport_config(), QQServerConfig)
    assert isinstance(server.transport_config(), QQReverseServerConfig)


def test_server_runtime_validation_requires_auth_and_valid_listener():
    settings = QQPluginSettings.model_validate({"plugin": {"enabled": True, "transport_mode": "server"}})
    assert not settings.validate_runtime_config(logging.getLogger("test"))
    settings.server.token = "token"
    settings.server.listen_host = ""
    assert not settings.validate_runtime_config(logging.getLogger("test"))
    settings.server.listen_host = "127.0.0.1"
    settings.server.listen_port = 0
    assert not settings.validate_runtime_config(logging.getLogger("test"))


def test_path_normalization():
    config = QQReverseServerConfig.model_validate({"listen_path": "onebot/v11/ws"})
    assert config.normalized_path() == "/onebot/v11/ws"


def test_legacy_migration_preserves_server_section():
    result = QQPluginSettings._migrate_legacy_config({"server": {"token": "old-token"}})
    assert result["server"]["token"] == "old-token"


def test_hot_update_invalid_config_does_not_crash():
    """配置热更新模型校验失败时应抛出可捕获的 ValueError，而不是破坏插件状态。"""
    from snowluma_reverse.config import QQPluginSettings as Settings

    with pytest.raises(ValueError):
        Settings.model_validate({"plugin": {"transport_mode": 123}})
    valid = Settings.model_validate({"plugin": {"transport_mode": "server"}})
    assert valid.transport_config() is valid.server

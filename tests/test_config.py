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

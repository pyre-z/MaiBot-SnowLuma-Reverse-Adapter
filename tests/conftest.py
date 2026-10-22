"""共享测试工具。"""

import logging
import socket
from types import SimpleNamespace

import pytest


@pytest.fixture
def logger():
    return logging.getLogger("snowluma-test")


@pytest.fixture
def server_config():
    """生成使用临时可用端口的反向服务配置。"""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    path = "/onebot/v11/ws"
    return SimpleNamespace(
        listen_host="127.0.0.1", listen_port=port, listen_path=path,
        token="test-token", allowed_ips=[], expect_self_id="",
        heartbeat_interval=30.0, action_timeout_sec=5.0,
        max_message_size=16 * 1024 * 1024, connection_id="",
        normalized_path=lambda: path,
    )



def make_reverse_config(**overrides):
    """构造独立的反向服务端配置对象，供需要多个端口或自定义字段的测试使用。"""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    values = {
        "listen_host": "127.0.0.1",
        "listen_port": port,
        "listen_path": "/onebot/v11/ws",
        "token": "test-token",
        "allowed_ips": [],
        "expect_self_id": "",
        "heartbeat_interval": 30.0,
        "action_timeout_sec": 5.0,
        "max_message_size": 16 * 1024 * 1024,
        "connection_id": "",
    }
    values.update(overrides)
    path = values["listen_path"]
    return SimpleNamespace(**values, normalized_path=lambda: path)

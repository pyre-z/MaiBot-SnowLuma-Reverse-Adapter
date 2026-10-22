"""反向传输鉴权与健康端点测试。"""

from types import SimpleNamespace

import aiohttp
import pytest

from snowluma_reverse.transport.auth import authorize_request, is_ip_allowed
from snowluma_reverse.transport.reverse_server import QQTransportServer


class Request:
    remote = "127.0.0.1"

    def __init__(self, headers=None, query=None):
        self.headers = headers or {}
        self.query = query or {}


@pytest.mark.parametrize(
    "auth_request",
    [Request({"Authorization": "Bearer secret"}), Request(query={"access_token": "secret"})],
)
def test_token_channels_accept_and_reject(auth_request):
    cfg = SimpleNamespace(token="secret", allowed_ips=[])
    assert authorize_request(auth_request, cfg) == (True, "")
    assert authorize_request(Request({"Authorization": "Bearer bad"}), cfg)[0] is False
    assert authorize_request(Request(query={"access_token": "bad"}), cfg)[0] is False


def test_start_requires_authentication(logger, server_config):
    server_config.token = ""
    server_config.allowed_ips = []
    transport = QQTransportServer(logger, _noop, _noop, _payload)
    transport.configure(server_config)
    with pytest.raises(RuntimeError, match="未配置 token"):
        import asyncio
        asyncio.run(transport.start())


def test_ip_allowlist_supports_address_and_cidr():
    assert is_ip_allowed("192.0.2.10", ["192.0.2.10"])
    assert is_ip_allowed("192.0.2.10", ["192.0.2.0/24"])
    assert not is_ip_allowed("198.51.100.1", ["192.0.2.0/24"])
    cfg = SimpleNamespace(token="", allowed_ips=["192.0.2.0/24"])
    assert authorize_request(Request(), cfg) == (False, "来源 IP 不在白名单内")


async def _noop():
    return None


async def _payload(_value):
    return None


@pytest.mark.asyncio
async def test_expect_self_id_and_health_visibility(logger, server_config):
    server_config.expect_self_id = "10001"
    server = QQTransportServer(logger, _noop, _noop, _payload)
    server.configure(server_config)
    await server.start()
    base = f"http://{server_config.listen_host}:{server_config.listen_port}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(base + "/healthz") as response:
                data = await response.json()
                assert response.status == 200
                assert "self_id" not in data
            async with session.get(base + "/healthz", headers={"Authorization": "Bearer test-token"}) as response:
                assert "self_id" in await response.json()
            for headers in ({"Authorization": "Bearer test-token", "X-Self-ID": "99999"},
                            {"Authorization": "Bearer test-token"}):
                ws = await session.ws_connect(base + server_config.listen_path, headers=headers)
                await ws.receive(timeout=2)
                assert ws.close_code == 1008
                await ws.close()
            ws = await session.ws_connect(
                base + server_config.listen_path,
                headers={"Authorization": "Bearer test-token", "X-Self-ID": "10001"},
            )
            await ws.close()
    finally:
        await server.stop()

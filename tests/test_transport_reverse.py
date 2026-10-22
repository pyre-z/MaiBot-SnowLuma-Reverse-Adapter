"""反向 WebSocket 传输回归测试。"""

import asyncio
import json

import aiohttp
import pytest

from snowluma_reverse.transport.reverse_server import QQTransportServer


class Recorder:
    def __init__(self):
        self.payloads = []

    async def opened(self):
        return None

    async def closed(self):
        return None

    async def payload(self, value):
        self.payloads.append(value)


@pytest.fixture
async def server(server_config, logger):
    recorder = Recorder()
    instance = QQTransportServer(logger, recorder.opened, recorder.closed, recorder.payload)
    instance.configure(server_config)
    await instance.start()
    try:
        yield instance, recorder, server_config
    finally:
        await instance.stop()


async def connect(config, self_id="10001", token="test-token"):
    session = aiohttp.ClientSession()
    try:
        ws = await session.ws_connect(
            f"http://{config.listen_host}:{config.listen_port}{config.listen_path}",
            headers={"X-Self-ID": self_id, "Authorization": f"Bearer {token}"},
        )
    except BaseException:
        await session.close()
        raise
    return session, ws


@pytest.mark.asyncio
async def test_wrong_token_returns_401(server):
    _, _, config = server
    with pytest.raises(aiohttp.WSServerHandshakeError) as error:
        await connect(config, token="wrong")
    assert error.value.status == 401


@pytest.mark.asyncio
async def test_event_and_action_echo_on_same_connection(server):
    instance, recorder, config = server
    session, ws = await connect(config)
    try:
        await ws.send_json({"post_type": "message", "raw_message": "hello"})
        for _ in range(30):
            if recorder.payloads:
                break
            await asyncio.sleep(0.05)
        assert recorder.payloads == [{"post_type": "message", "raw_message": "hello"}]

        async def answer():
            message = await ws.receive(timeout=3)
            request = json.loads(message.data)
            await ws.send_json({"status": "ok", "retcode": 0, "data": {"echo": True}, "echo": request["echo"]})

        responder = asyncio.create_task(answer())
        response = await instance.call_action("get_group_info", {"group_id": 123})
        await responder
        assert response["data"]["echo"] is True
    finally:
        await ws.close()
        await session.close()


@pytest.mark.asyncio
async def test_idle_connection_survives_twelve_seconds(server):
    _, _, config = server
    session, ws = await connect(config)
    try:
        await asyncio.sleep(12)
        assert not ws.closed
    finally:
        await ws.close()
        await session.close()


@pytest.mark.asyncio
async def test_self_id_concurrency_and_same_account_replacement(server):
    _, _, config = server
    session_a, ws_a = await connect(config, "10001")
    session_b, ws_b = await connect(config, "20002")
    try:
        await ws_b.receive(timeout=2)
        assert ws_b.close_code == 1008
        session_c, ws_c = await connect(config, "10001")
        try:
            await ws_a.receive(timeout=3)
            assert ws_a.close_code == 1001
        finally:
            await ws_c.close()
            await session_c.close()
    finally:
        await ws_a.close()
        await session_a.close()
        await ws_b.close()
        await session_b.close()


@pytest.mark.asyncio
async def test_call_action_without_connection_raises(server):
    instance, _, _ = server
    with pytest.raises(RuntimeError):
        await instance.call_action("get_login_info", {})

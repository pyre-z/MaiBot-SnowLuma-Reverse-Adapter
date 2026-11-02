"""反向 WS 连接池（多 slot）回归测试。"""

import asyncio
import json

import aiohttp
import pytest

from snowluma_reverse.transport.connection_pool import ConnectionPool, SlotConnection
from snowluma_reverse.transport.reverse_server import QQTransportServer
from tests.conftest import make_reverse_config


class Recorder:
    def __init__(self):
        self.payloads = []
        self.opened = 0
        self.closed = 0

    async def on_opened(self):
        self.opened += 1

    async def on_closed(self):
        self.closed += 1

    async def on_payload(self, value):
        self.payloads.append(value)


async def start_server(logger, **overrides):
    recorder = Recorder()
    config = make_reverse_config(**overrides)
    instance = QQTransportServer(
        logger, recorder.on_opened, recorder.on_closed, recorder.on_payload
    )
    instance.configure(config)
    await instance.start()
    return instance, recorder, config


async def connect(config, *, slot="", self_id="10001", role="Universal", token="test-token"):
    session = aiohttp.ClientSession()
    path = config.normalized_path() if not slot else f"{config.normalized_path()}/{slot}"
    headers = {"X-Self-ID": self_id, "Authorization": f"Bearer {token}", "X-Client-Role": role}
    try:
        ws = await session.ws_connect(
            f"http://{config.listen_host}:{config.listen_port}{path}", headers=headers
        )
    except BaseException:
        await session.close()
        raise
    return session, ws


async def answer_once(ws, data=None):
    """读取一条动作请求并回写成功响应。"""

    message = await ws.receive(timeout=3)
    request = json.loads(message.data)
    await ws.send_json(
        {"status": "ok", "retcode": 0, "data": data or {"ok": True}, "echo": request["echo"]}
    )
    return request


@pytest.mark.asyncio
async def test_slot_path_registers_independent_entries(logger):
    instance, _, config = await start_server(logger)
    session_a, ws_a = await connect(config, slot="", role="Universal")
    session_b, ws_b = await connect(config, slot="1", role="Api")
    try:
        await asyncio.sleep(0.2)
        slots = {item.slot: item for item in instance._pool.connections()}
        assert set(slots) == {"0", "1"}
        assert slots["0"].role == "universal"
        assert slots["1"].role == "api"
        assert slots["0"].send_lock is not slots["1"].send_lock
        assert slots["1"].pending is not slots["0"].pending
    finally:
        await ws_a.close()
        await ws_b.close()
        await session_a.close()
        await session_b.close()
        await instance.stop()


@pytest.mark.asyncio
async def test_stalled_action_on_one_slot_does_not_block_another(logger):
    instance, _, config = await start_server(logger)
    session_a, ws_a = await connect(config, slot="", role="Universal")
    session_b, ws_b = await connect(config, slot="1", role="Api")
    try:
        await asyncio.sleep(0.2)

        # round_robin 下第一次落到 slot=1；该动作故意不回响应，模拟大消息占住链路。
        stalled = asyncio.create_task(
            instance.call_action("send_private_msg", {"user_id": 1}, slot="1")
        )
        request = json.loads((await ws_b.receive(timeout=3)).data)
        assert request["action"] == "send_private_msg"

        # 第二条动作必须能落到 slot=0 并立即完成，而不是排队等 slot=1 的锁。
        responder = asyncio.create_task(answer_once(ws_a, {"message_id": 42}))
        response = await asyncio.wait_for(
            instance.call_action("send_group_msg", {"group_id": 2}), timeout=2
        )
        await responder
        assert response["data"]["message_id"] == 42

        # 释放被占住的 slot=1。
        await ws_b.send_json(
            {"status": "ok", "retcode": 0, "data": {"message_id": 1}, "echo": request["echo"]}
        )
        stalled_result = await asyncio.wait_for(stalled, timeout=3)
        assert stalled_result["data"]["message_id"] == 1
    finally:
        await ws_a.close()
        await ws_b.close()
        await session_a.close()
        await session_b.close()
        await instance.stop()


@pytest.mark.asyncio
async def test_event_channel_is_unique_and_moves_to_newest_slot(logger):
    instance, recorder, config = await start_server(logger)
    session_a, ws_a = await connect(config, slot="", role="Universal")
    await asyncio.sleep(0.2)
    session_b, ws_b = await connect(config, slot="2", role="Universal")
    try:
        await ws_a.receive(timeout=3)
        assert ws_a.close_code == 1001

        await ws_b.send_json({"post_type": "message", "raw_message": "from-slot-2"})
        for _ in range(40):
            if recorder.payloads:
                break
            await asyncio.sleep(0.05)
        assert recorder.payloads == [{"post_type": "message", "raw_message": "from-slot-2"}]
    finally:
        await ws_b.close()
        await session_a.close()
        await session_b.close()
        await instance.stop()


@pytest.mark.asyncio
async def test_api_slot_does_not_receive_events(logger):
    instance, recorder, config = await start_server(logger)
    session_a, ws_a = await connect(config, slot="", role="Universal")
    session_b, ws_b = await connect(config, slot="1", role="Api")
    try:
        await asyncio.sleep(0.2)
        await ws_b.send_json({"post_type": "message", "raw_message": "should-be-ignored"})
        await ws_a.send_json({"post_type": "message", "raw_message": "kept"})
        for _ in range(40):
            if recorder.payloads:
                break
            await asyncio.sleep(0.05)
        await asyncio.sleep(0.2)
        assert recorder.payloads == [{"post_type": "message", "raw_message": "kept"}]
    finally:
        await ws_a.close()
        await ws_b.close()
        await session_a.close()
        await session_b.close()
        await instance.stop()


@pytest.mark.asyncio
async def test_idle_slot_is_recycled_but_event_slot_is_kept(logger):
    instance, _, config = await start_server(logger, slot_idle_timeout_sec=1.0)
    session_a, ws_a = await connect(config, slot="", role="Universal")
    session_b, ws_b = await connect(config, slot="3", role="Api")
    try:
        for _ in range(60):
            if instance._pool.get("3") is None:
                break
            await asyncio.sleep(0.1)
        assert instance._pool.get("3") is None
        # 客户端要读到 close 帧才会把 closed 置位。
        message = await ws_b.receive(timeout=3)
        assert message.type is aiohttp.WSMsgType.CLOSE
        assert not ws_a.closed
        assert {item.slot for item in instance._pool.connections()} == {"0"}
    finally:
        await ws_a.close()
        await session_a.close()
        await session_b.close()
        await instance.stop()


@pytest.mark.asyncio
async def test_health_endpoint_lists_slots(logger):
    instance, _, config = await start_server(logger)
    session_a, ws_a = await connect(config, slot="", role="Universal")
    session_b, ws_b = await connect(config, slot="1", role="Api")
    try:
        await asyncio.sleep(0.2)
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://{config.listen_host}:{config.listen_port}/healthz",
                params={"access_token": "test-token"},
            ) as response:
                payload = await response.json()
        assert payload["connected"] is True
        assert payload["slot_count"] == 2
        assert {item["slot"] for item in payload["slots"]} == {"0", "1"}
    finally:
        await ws_a.close()
        await ws_b.close()
        await session_a.close()
        await session_b.close()
        await instance.stop()


class _FakeWS:
    closed = False


def test_pick_prefers_idle_slot_for_queries():
    pool = ConnectionPool()
    pool.add(SlotConnection(slot="0", ws=_FakeWS(), role="api"))
    pool.add(SlotConnection(slot="1", ws=_FakeWS(), role="api"))
    pool.get("0").in_flight = 1

    # 查询类动作不要求保序，直接挑最空闲的槽位。
    assert pool.pick({"group_id": 1}, ordered=False).slot == "1"
    # 发送类动作保持会话粘性，不会因为另一条路空闲就换槽位。
    assert pool.pick({"group_id": 1}).slot == pool.pick({"group_id": 1}).slot


def test_pick_returns_none_without_send_capable_slot():
    pool = ConnectionPool()
    pool.add(SlotConnection(slot="0", ws=_FakeWS(), role="event"))
    assert pool.pick({}) is None

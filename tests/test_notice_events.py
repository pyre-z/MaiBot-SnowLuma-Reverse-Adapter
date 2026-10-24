from types import SimpleNamespace

import pytest

from snowluma_reverse.config.sections import QQNoticeConfig
from snowluma_reverse.filters import QQNoticeFilter
from snowluma_reverse.protocol.notice import QQNoticeCodec
from snowluma_reverse.runtime.router import QQEventRouter


class Query:
    def __getattr__(self, name):
        async def query(*args, **kwargs):
            return None
        return query


@pytest.fixture
def notice_codec(logger):
    return QQNoticeCodec(logger, Query())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"notice_type": "bot_offline", "self_id": "100", "user_id": "100", "tag": "offline", "message": "lost"},
        {"notice_type": "essence", "sub_type": "add", "group_id": "200", "user_id": "2", "operator_id": "3", "message_id": "4"},
        {"notice_type": "friend_add", "user_id": "2"},
        {"notice_type": "friend_recall", "user_id": "2", "message_id": "4"},
        {"notice_type": "group_admin", "sub_type": "set", "group_id": "200", "user_id": "2"},
        {"notice_type": "group_ban", "sub_type": "ban", "group_id": "200", "user_id": "2", "operator_id": "3", "duration": 60},
        {"notice_type": "group_card", "group_id": "200", "user_id": "2", "card_new": "new", "card_old": "old"},
        {"notice_type": "group_decrease", "sub_type": "leave", "group_id": "200", "user_id": "2", "operator_id": "3"},
        {"notice_type": "group_increase", "sub_type": "approve", "group_id": "200", "user_id": "2", "operator_id": "3"},
        {"notice_type": "group_msg_emoji_like", "group_id": "200", "user_id": "2", "message_id": "4", "likes": []},
        {"notice_type": "group_recall", "group_id": "200", "user_id": "2", "operator_id": "3", "message_id": "4"},
        {"notice_type": "group_upload", "group_id": "200", "user_id": "2", "file": {"name": "x", "size": 4, "id": "f"}},
        {"notice_type": "notify", "sub_type": "poke", "user_id": "2", "target_id": "100"},
    ],
)
async def test_all_notice_types_build_nonempty_host_notice(notice_codec, payload):
    payload.setdefault("self_id", "100")
    result = await notice_codec.build_notice_message_dict(payload)
    assert result is not None
    assert result["is_notify"] is True
    assert result["processed_plain_text"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"sub_type": "poke", "user_id": "2", "target_id": "3"},
        {"sub_type": "group_name", "group_id": "4", "user_id": "2", "name_new": "new"},
        {"sub_type": "title", "group_id": "4", "user_id": "2", "title": "owner"},
        {"sub_type": "input_status", "user_id": "2", "event_type": 1, "status_text": "typing"},
        {"sub_type": "profile_like", "user_id": "2", "times": 3},
    ],
)
async def test_all_notify_subtypes(payload, notice_codec):
    payload.update(notice_type="notify", self_id="100")
    result = await notice_codec.build_notice_message_dict(payload)
    assert result is not None and result["processed_plain_text"]


def test_input_status_filter_defaults_off_and_can_be_enabled():
    filter_ = QQNoticeFilter(None)
    config = QQNoticeConfig()
    assert config.forward_input_status is False
    assert not filter_.is_notice_event_allowed("notify", "input_status", config)
    config.forward_input_status = True
    assert filter_.is_notice_event_allowed("notify", "input_status", config)


@pytest.mark.asyncio
async def test_unknown_notice_type_is_dropped_before_queue(logger):
    routed = []
    router = QQEventRouter(SimpleNamespace(route_message=lambda **kwargs: routed.append(kwargs)), logger, "test", lambda: None)
    router.bind_runtime(SimpleNamespace())
    await router.handle_notice_event({"notice_type": "future_notice", "self_id": "100"})
    assert routed == []


@pytest.mark.asyncio
async def test_bot_offline_reports_disconnected(logger):
    calls = []

    class State:
        async def report_disconnected(self):
            calls.append("disconnected")

    class Router(QQEventRouter):
        async def route_notice_payload(self, payload, self_id, connection_id):
            calls.append("notice")

    runtime = SimpleNamespace(runtime_state=State())
    settings = SimpleNamespace(server=SimpleNamespace(connection_id=""))
    router = Router(SimpleNamespace(), logger, "test", lambda: settings)
    router.bind_runtime(runtime)
    await router.handle_notice_event({"notice_type": "bot_offline", "self_id": "100", "user_id": "100"})
    assert calls == ["notice", "disconnected"]

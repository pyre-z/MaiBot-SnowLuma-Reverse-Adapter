"""撤回通知：区分「谁撤回的」，避免机器人自撤回被读成对方撤回。"""

import pytest

from snowluma_reverse.protocol.notice import QQNoticeCodec


class Query:
    """展示名查询桩：一律返回 None，走默认名。"""

    def __getattr__(self, name):
        async def query(*args, **kwargs):
            return None

        return query


@pytest.fixture
def notice_codec(logger):
    return QQNoticeCodec(logger, Query())


async def _render(notice_codec, payload):
    result = await notice_codec.build_notice_message_dict(payload)
    assert result is not None
    return result["processed_plain_text"]


@pytest.mark.asyncio
async def test_friend_recall_by_bot_says_self(notice_codec):
    text = await _render(
        notice_codec,
        {"notice_type": "friend_recall", "user_id": "100", "message_id": "4", "self_id": "100"},
    )
    assert "你撤回了自己的一条消息" in text
    assert "你撤回" in text


@pytest.mark.asyncio
async def test_friend_recall_by_other_user_unchanged(notice_codec):
    text = await _render(
        notice_codec,
        {"notice_type": "friend_recall", "user_id": "2", "message_id": "4", "self_id": "100"},
    )
    assert "撤回了一条消息" in text
    assert "你撤回" not in text


@pytest.mark.asyncio
async def test_group_recall_operator_is_bot(notice_codec):
    text = await _render(
        notice_codec,
        {
            "notice_type": "group_recall",
            "group_id": "200",
            "user_id": "2",
            "operator_id": "100",
            "message_id": "4",
            "self_id": "100",
        },
    )
    assert text.startswith("[事件-群消息撤回] 你撤回了")
    assert "的消息" in text


@pytest.mark.asyncio
async def test_group_recall_bot_message_recalled_by_other(notice_codec):
    text = await _render(
        notice_codec,
        {
            "notice_type": "group_recall",
            "group_id": "200",
            "user_id": "100",
            "operator_id": "3",
            "message_id": "4",
            "self_id": "100",
        },
    )
    assert "撤回了你的消息" in text


@pytest.mark.asyncio
async def test_group_recall_between_other_users_unchanged(notice_codec):
    text = await _render(
        notice_codec,
        {
            "notice_type": "group_recall",
            "group_id": "200",
            "user_id": "2",
            "operator_id": "3",
            "message_id": "4",
            "self_id": "100",
        },
    )
    assert "你撤回" not in text
    assert "你的消息" not in text

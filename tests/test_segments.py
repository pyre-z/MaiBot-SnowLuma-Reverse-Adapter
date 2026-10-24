from types import SimpleNamespace

import pytest

from snowluma_reverse.profile import ProfileState, SNOWLUMA_PROFILE
from snowluma_reverse.protocol.inbound import QQInboundCodec
from snowluma_reverse.protocol.outbound.segment_encoder import QQOutboundSegmentEncoder


class Query:
    def __getattr__(self, name):
        async def query(*args, **kwargs):
            return None
        return query


def _codec_for_mode(logger, mode: str):
    return QQInboundCodec(
        logger,
        Query(),
        ProfileState(SNOWLUMA_PROFILE),
        lambda: SimpleNamespace(plugin=SimpleNamespace(qq_face_parse_mode=mode)),
    )


@pytest.fixture
def codec(logger):
    return _codec_for_mode(logger, "description")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("segment_type", "data", "expected"),
    [
        ("text", {"text": "hello"}, "hello"),
        ("at", {"qq": "1"}, None),
        ("face", {"id": "9999"}, "[小表情·未知表情#9999]"),
        ("image", {"file": ""}, "[image]"),
        ("record", {"file": "x"}, "[voice]"),
        ("video", {"file": "x"}, None),
        ("file", {"name": "x.txt", "size": 4}, None),
        ("flash_file", {"title": "flash.txt", "file_set_id": "42", "thumb": "https://x"}, "flash.txt"),
        ("forward", {"id": "missing"}, "[forward]"),
        ("json", {"data": "{}"}, None),
        ("xml", {"data": "x"}, "[xml]"),
        ("mface", {"summary": "[笑]"}, "[笑]"),
        ("markdown", {"content": "**bold**"}, "**bold**"),
        ("reply", {"id": "0"}, None),
        ("poke", {"type": 1}, "[戳一戳]"),
        ("inline_keyboard", {"rows": [{"buttons": [{"label": "secret"}]}]}, "[内联键盘]"),
    ],
)
async def test_all_snowluma_segments_decode(codec, segment_type, data, expected):
    converted, _ = await codec.convert_segments({"message": [{"type": segment_type, "data": data}]}, "1")
    assert converted is not None
    if expected is not None:
        assert expected in " ".join(str(part.get("data", "")) for part in converted)


@pytest.mark.asyncio
async def test_unknown_segment_degrades_to_placeholder(codec):
    converted, _ = await codec.convert_segments({"message": [{"type": "future_segment", "data": {}}]}, "1")
    assert converted == [{"type": "text", "data": "[不支持的消息段: future_segment]"}]


@pytest.mark.asyncio
async def test_description_mode_emits_anchor_with_name_and_id(logger):
    converted, _ = await _codec_for_mode(logger, "description").convert_segments(
        {"message": [{"type": "face", "data": {"id": "187"}}]}, "1"
    )
    assert converted == [{"type": "text", "data": "[小表情·幽灵#187]"}]


@pytest.mark.asyncio
async def test_description_mode_marks_unknown_face(logger):
    converted, _ = await _codec_for_mode(logger, "description").convert_segments(
        {"message": [{"type": "face", "data": {"id": "9999"}}]}, "1"
    )
    assert converted == [{"type": "text", "data": "[小表情·未知表情#9999]"}]


@pytest.mark.asyncio
async def test_emoji_mode_prefers_unicode_emoji(logger):
    from snowluma_reverse.data.faces import QQ_FACE_EMOJIS

    face_id, emoji = next(iter(QQ_FACE_EMOJIS.items()))
    converted, _ = await _codec_for_mode(logger, "emoji").convert_segments(
        {"message": [{"type": "face", "data": {"id": face_id}}]}, "1"
    )
    assert converted == [{"type": "text", "data": emoji}]


def test_unsupported_outbound_snowluma_segments_degrade_to_text():
    encoded = QQOutboundSegmentEncoder().convert_segments([
        {"type": "mface", "data": {"emoji_id": "abc"}},
        {"type": "inline_keyboard", "data": {"rows": []}},
    ])
    assert encoded == [
        {"type": "text", "data": {"text": "[mface]"}},
        {"type": "text", "data": {"text": "[inline_keyboard]"}},
    ]

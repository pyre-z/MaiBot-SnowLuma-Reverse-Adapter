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


@pytest.fixture
def codec(logger):
    return QQInboundCodec(logger, Query(), ProfileState(SNOWLUMA_PROFILE), lambda: SimpleNamespace(plugin=SimpleNamespace(qq_face_parse_mode="description")))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("segment_type", "data", "expected"),
    [
        ("text", {"text": "hello"}, "hello"),
        ("at", {"qq": "1"}, None),
        ("face", {"id": "9999"}, "[表情]"),
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


def test_unsupported_outbound_snowluma_segments_degrade_to_text():
    encoded = QQOutboundSegmentEncoder().convert_segments([
        {"type": "mface", "data": {"emoji_id": "abc"}},
        {"type": "inline_keyboard", "data": {"rows": []}},
    ])
    assert encoded == [
        {"type": "text", "data": {"text": "[mface]"}},
        {"type": "text", "data": {"text": "[inline_keyboard]"}},
    ]

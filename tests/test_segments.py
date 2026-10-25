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


def test_face_token_converts_known_numeric_id():
    encoder = QQOutboundSegmentEncoder(enable_text_face_token=lambda: True)
    assert encoder.convert_segments([{"type": "text", "data": "先[小表情#187]再"}]) == [
        {"type": "text", "data": {"text": "先"}},
        {"type": "face", "data": {"id": "187"}},
        {"type": "text", "data": {"text": "再"}},
    ]


def test_face_token_keeps_unknown_and_symbolic_ids():
    encoder = QQOutboundSegmentEncoder(enable_text_face_token=lambda: True)
    raw = "[小表情#99999][小表情#☀][小表情#][小表情#abc]"
    assert encoder.convert_segments([{"type": "text", "data": raw}]) == [
        {"type": "text", "data": {"text": raw}}
    ]


def test_face_token_switch_off_keeps_text():
    encoder = QQOutboundSegmentEncoder(enable_text_face_token=lambda: False)
    assert encoder.convert_segments([{"type": "text", "data": "[小表情#187]"}]) == [
        {"type": "text", "data": {"text": "[小表情#187]"}}
    ]


def test_face_token_ignores_inbound_anchor():
    encoder = QQOutboundSegmentEncoder(enable_text_face_token=lambda: True)
    raw = "[小表情·幽灵#187]"
    assert encoder.convert_segments([{"type": "text", "data": raw}]) == [
        {"type": "text", "data": {"text": raw}}
    ]


def test_face_token_and_name_conversion_combine():
    encoder = QQOutboundSegmentEncoder(
        enable_text_face_conversion=lambda: True,
        enable_text_face_token=lambda: True,
    )
    assert encoder.convert_segments([{"type": "text", "data": "/幽灵[小表情#0]"}]) == [
        {"type": "face", "data": {"id": "187"}},
        {"type": "face", "data": {"id": "0"}},
    ]


def test_face_name_token_converts_legacy_chinese_name():
    encoder = QQOutboundSegmentEncoder(enable_text_face_name_token=lambda: True)
    assert encoder.convert_segments([{"type": "text", "data": "何止贵，简直吞金兽[汗]"}]) == [
        {"type": "text", "data": {"text": "何止贵，简直吞金兽"}},
        {"type": "face", "data": {"id": "278"}},
    ]


def test_face_name_token_matches_longest_name_first():
    encoder = QQOutboundSegmentEncoder(enable_text_face_name_token=lambda: True)
    assert encoder.convert_segments([{"type": "text", "data": "[流汗][吃瓜]"}]) == [
        {"type": "face", "data": {"id": "27"}},
        {"type": "face", "data": {"id": "271"}},
    ]


def test_face_name_token_keeps_unknown_brackets():
    encoder = QQOutboundSegmentEncoder(enable_text_face_name_token=lambda: True)
    raw = "[图片][注][表情包][汗汗]"
    assert encoder.convert_segments([{"type": "text", "data": raw}]) == [
        {"type": "text", "data": {"text": raw}}
    ]


def test_face_name_token_switch_off_keeps_text():
    encoder = QQOutboundSegmentEncoder(enable_text_face_name_token=lambda: False)
    raw = "何止贵，简直吞金兽[汗]"
    assert encoder.convert_segments([{"type": "text", "data": raw}]) == [
        {"type": "text", "data": {"text": raw}}
    ]


def test_face_name_token_ignores_anchor_and_id_token():
    encoder = QQOutboundSegmentEncoder(
        enable_text_face_token=lambda: True,
        enable_text_face_name_token=lambda: True,
    )
    raw = "[小表情·幽灵#187][小表情#187]"
    assert encoder.convert_segments([{"type": "text", "data": raw}]) == [
        {"type": "text", "data": {"text": "[小表情·幽灵#187]"}},
        {"type": "face", "data": {"id": "187"}},
    ]


def _outbound_actions(codec, raw_message, *, group_id="", user_id="10001000"):
    message = {
        "account_id": "10002000",
        "message_info": {"group_info": {"group_id": group_id} if group_id else {}},
        "raw_message": raw_message,
    }
    route = {"group_id": group_id, "user_id": user_id}
    return codec.build_outbound_actions(message, route)


def test_private_outbound_drops_at_but_keeps_text():
    from snowluma_reverse.protocol.outbound.message_codec import QQOutboundCodec

    codec = QQOutboundCodec(ProfileState(SNOWLUMA_PROFILE))
    actions = _outbound_actions(
        codec,
        [
            {"type": "at", "data": {"target_user_id": "10001000"}},
            {"type": "text", "data": "确实抠[吃瓜]"},
        ],
    )
    _, params = actions[0]
    assert [segment["type"] for segment in params["message"]] == ["text"]
    assert params["message"][0]["data"]["text"] == "确实抠[吃瓜]"


def test_group_outbound_keeps_at():
    from snowluma_reverse.protocol.outbound.message_codec import QQOutboundCodec

    codec = QQOutboundCodec(ProfileState(SNOWLUMA_PROFILE))
    actions = _outbound_actions(
        codec,
        [
            {"type": "at", "data": {"target_user_id": "10001000"}},
            {"type": "text", "data": "看这个"},
        ],
        group_id="123456",
    )
    _, params = actions[0]
    assert [segment["type"] for segment in params["message"]] == ["at", "text"]


def test_private_outbound_pure_at_falls_back_to_empty_text():
    from snowluma_reverse.protocol.outbound.message_codec import QQOutboundCodec

    codec = QQOutboundCodec(ProfileState(SNOWLUMA_PROFILE))
    actions = _outbound_actions(codec, [{"type": "at", "data": {"target_user_id": "10001000"}}])
    _, params = actions[0]
    assert params["message"] == [{"type": "text", "data": {"text": ""}}]


def test_pangu_spacing_basic_and_idempotent():
    from snowluma_reverse.protocol.outbound.pangu import apply_pangu_spacing

    cases = {
        "这是Flash吧": "这是 Flash 吧",
        "中文English混合": "中文 English 混合",
        "输出68元/MTok": "输出 68 元/MTok",
        "中文 English 已带空格": "中文 English 已带空格",
        "纯中文没有字母": "纯中文没有字母",
    }
    for source, expected in cases.items():
        assert apply_pangu_spacing(source) == expected
        assert apply_pangu_spacing(expected) == expected


def test_pangu_spacing_digits_switch():
    from snowluma_reverse.protocol.outbound.pangu import apply_pangu_spacing

    assert apply_pangu_spacing("说了5个人", spacing_digits=True) == "说了 5 个人"
    assert apply_pangu_spacing("说了5个人", spacing_digits=False) == "说了5个人"
    assert apply_pangu_spacing("说ABC了", spacing_digits=False) == "说 ABC 了"


def test_pangu_spacing_protects_tokens_urls_and_code():
    from snowluma_reverse.protocol.outbound.pangu import apply_pangu_spacing

    unchanged = [
        "[小表情#271]吃瓜中",
        "看这个https://bot.example.com/onebot/v11/ws就行了",
        "用/捂脸试试",
        "代码`x=1`和`中文`混排",
    ]
    for source in unchanged:
        assert apply_pangu_spacing(source) == source
    # 方括号本身不被插入空格，但括号外的中英边界照常处理
    assert apply_pangu_spacing("[思考]这不QQ表情") == "[思考]这不 QQ 表情"


def test_encoder_pangu_keeps_face_token_split():
    encoder = QQOutboundSegmentEncoder(
        enable_text_face_token=lambda: True,
        enable_pangu_spacing=lambda: True,
    )
    assert encoder.convert_segments([{"type": "text", "data": "中文[小表情#271]English"}]) == [
        {"type": "text", "data": {"text": "中文"}},
        {"type": "face", "data": {"id": "271"}},
        {"type": "text", "data": {"text": "English"}},
    ]


def test_encoder_pangu_switch_off_keeps_text():
    encoder = QQOutboundSegmentEncoder(enable_pangu_spacing=lambda: False)
    assert encoder.convert_segments([{"type": "text", "data": "这是Flash吧"}]) == [
        {"type": "text", "data": {"text": "这是Flash吧"}}
    ]


def test_private_at_kept_when_strip_switch_off():
    from snowluma_reverse.protocol.outbound.message_codec import QQOutboundCodec

    codec = QQOutboundCodec(ProfileState(SNOWLUMA_PROFILE), enable_private_at_strip=lambda: False)
    actions = _outbound_actions(
        codec,
        [
            {"type": "at", "data": {"target_user_id": "10001000"}},
            {"type": "text", "data": "看这个"},
        ],
    )
    _, params = actions[0]
    assert [segment["type"] for segment in params["message"]] == ["at", "text"]


def test_strip_trailing_chat_punctuation():
    from snowluma_reverse.protocol.outbound.text_style import strip_trailing_chat_punctuation as strip

    cases = {
        "好的。": "好的",
        "我总结一下：": "我总结一下",
        "好的： ": "好的",
        "真的。。。": "真的。。。",
        "好吧。。": "好吧。。",
        "好。：": "好。：",
        "第一。第二": "第一。第二",
        "真的吗？": "真的吗？",
        "确实！": "确实！",
        "。": "。",
        "纯文本": "纯文本",
        "": "",
    }
    for source, expected in cases.items():
        assert strip(source) == expected


def test_encoder_strips_trailing_punctuation():
    encoder = QQOutboundSegmentEncoder(
        enable_text_face_token=lambda: True,
        enable_trailing_punctuation_strip=lambda: True,
    )
    assert encoder.convert_segments([{"type": "text", "data": "好的。"}]) == [
        {"type": "text", "data": {"text": "好的"}}
    ]
    # 末尾是表情时，最后一个文本段同样清理
    assert encoder.convert_segments([{"type": "text", "data": "好的。[小表情#271]"}]) == [
        {"type": "text", "data": {"text": "好的"}},
        {"type": "face", "data": {"id": "271"}},
    ]


def test_encoder_trailing_punctuation_switch_off():
    encoder = QQOutboundSegmentEncoder(enable_trailing_punctuation_strip=lambda: False)
    assert encoder.convert_segments([{"type": "text", "data": "好的。"}]) == [
        {"type": "text", "data": {"text": "好的。"}}
    ]

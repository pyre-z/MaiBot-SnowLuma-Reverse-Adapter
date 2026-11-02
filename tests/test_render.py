"""聊天卡片渲染的离线测试（真实九宫格素材，不联网）。"""

import io
from pathlib import Path

from PIL import Image

from snowluma_reverse.render import (
    compose_bubble,
    parse_color,
    render_card,
    to_base64_source,
    wrap_text,
    load_font,
)

FIXTURE = Path(__file__).parent / "fixtures" / "bubble-2136042"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def load_slices() -> dict:
    return {path.stem: path.read_bytes() for path in FIXTURE.glob("*.png")}


def test_parse_color_handles_argb_and_rgb():
    assert parse_color("0xFF2554c1") == (0x25, 0x54, 0xC1, 0xFF)
    assert parse_color("#ffffff") == (255, 255, 255, 255)
    assert parse_color("") == (255, 255, 255, 255)
    assert parse_color(None, (1, 2, 3, 4)) == (1, 2, 3, 4)


def test_wrap_text_respects_pixel_width():
    font = load_font(24)
    from PIL import ImageDraw

    draw = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    lines = wrap_text(draw, "一二三四五六七八九十" * 6, font, 200)

    assert len(lines) > 1
    assert all(draw.textlength(line, font=font) <= 200 for line in lines)
    assert "".join(lines) == "一二三四五六七八九十" * 6


def test_wrap_text_by_char_count():
    font = load_font(24)
    from PIL import ImageDraw

    draw = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    text = "一二三四五六七八九十" * 3  # 30 个汉字
    lines = wrap_text(draw, text, font, max_chars=15)

    assert len(lines) == 2
    assert all(len(line) == 15 for line in lines)


def test_wrap_text_mixes_halfwidth_chars():
    font = load_font(24)
    from PIL import ImageDraw

    draw = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    lines = wrap_text(draw, "ababababababababababababababab" + "中文", font, max_chars=15)

    # 半角按 0.5 计，30 个字母正好一行
    assert len(lines) == 2
    assert lines[0].isascii() and len(lines[0]) == 30


def test_compose_bubble_stretches_to_requested_size():
    bubble = compose_bubble(load_slices(), 480, 140)

    assert bubble is not None
    assert bubble.size == (480, 140)
    # 角上的装饰画有透明留白，按区域判不透明像素即可
    def opaque(box):
        left, top, right, bottom = box
        return any(
            bubble.getpixel((x, y))[3] > 0
            for x in range(left, right, 3)
            for y in range(top, bottom, 3)
        )

    assert opaque((0, 0, 64, 64))       # 左上角装饰
    assert opaque((416, 0, 480, 64))    # 右上角装饰
    assert opaque((200, 40, 280, 100))  # 中间填充


def test_compose_bubble_clamps_below_corner_size():
    bubble = compose_bubble(load_slices(), 80, 60)

    assert bubble is not None
    # 不能小于「左上角 + 右上角」与「上角 + 下角」的尺寸
    assert bubble.width == 129
    assert bubble.height == 113


def test_compose_bubble_returns_none_without_corners():
    assert compose_bubble({}, 200, 80) is None


def test_render_card_produces_png():
    png = render_card(
        text="心收了，饭呢～",
        nickname="小鲸鱼",
        slices=load_slices(),
        text_color=(0x25, 0x54, 0xC1, 0xFF),
    )

    assert png.startswith(PNG_MAGIC)
    image = Image.open(io.BytesIO(png))
    assert image.width > 300 and image.height > 80


def test_render_card_mirror_flips_bubble():
    normal = Image.open(io.BytesIO(render_card(text="镜像测试", slices=load_slices()))).convert("RGB")
    mirrored = Image.open(io.BytesIO(render_card(text="镜像测试", slices=load_slices(), mirror=True))).convert("RGB")

    assert normal.size == mirrored.size

    # 气泡装饰带（不含文字）：正立时丝带在左，镜像后跑到右
    top, bottom = 45, 105
    band = (144, top, 409, bottom)
    left_side = (144, top, 200, bottom)
    right_side = (355, top, 409, bottom)

    assert list(normal.crop(band).getdata()) != list(mirrored.crop(band).getdata())
    assert list(normal.crop(left_side).getdata()) != list(mirrored.crop(left_side).getdata())
    assert list(normal.crop(right_side).getdata()) != list(mirrored.crop(right_side).getdata())


def test_render_card_without_nickname_is_shorter():
    with_nick = render_card(text="同一句", nickname="小鲸鱼", slices=load_slices())
    without = render_card(text="同一句", slices=load_slices())

    assert Image.open(io.BytesIO(without)).height < Image.open(io.BytesIO(with_nick)).height


def test_render_card_falls_back_without_slices():
    png = render_card(text="没有气泡素材时的兜底", slices={})

    assert png.startswith(PNG_MAGIC)


def test_base64_source_prefix():
    source = to_base64_source(b"\x89PNG\r\n\x1a\nfake")

    assert source.startswith("base64://")
    assert len(source) > len("base64://")

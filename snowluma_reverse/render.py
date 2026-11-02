"""把一条 QQ 消息渲染成聊天卡片（头像 + 气泡 + 文字）。

已知约束（实测 2026-11-02）：
- 气泡：appId=2，九宫格切图可用（角 64×56、边 2px、中心 2×2）
- 字体：appId=5 给的 ttf 是 178 个码位的子集，中文基本没有 → 一律用系统 CJK 字体
- 头像框：appId=4 只给宣传图（newPreview1.png），没有透明图层 → 不做头像框
"""

from __future__ import annotations

import io
from typing import Any, List, Mapping, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

# 容器里的兜底顺序：先找 Noto CJK，再退文泉驿，最后 unifont。
FONT_CANDIDATES: Tuple[str, ...] = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/unifont/unifont.otf",
)

# 中文方位标签 → 九宫格角色
CORNER_KEYS = {
    "tl": "左上角",
    "tr": "右上角",
    "bl": "左下角",
    "br": "右下角",
    "tm": "上边",
    "bm": "下边",
    "lm": "左边",
    "rm": "右边",
    "ct": "中心",
}

# 英文键（素材原始文件名）→ 九宫格角色，便于直接喂 fixtures / 原始切片
SLICE_STEMS = {
    "tl": "staticTopLeft",
    "tr": "staticTopRight",
    "bl": "staticBottomLeft",
    "br": "staticBottomRight",
    "tm": "staticTopMiddle",
    "bm": "staticBottomMiddle",
    "lm": "staticLeftMiddle",
    "rm": "staticRightMiddle",
    "ct": "staticAllMiddle",
}

BG_COLOR = (244, 245, 247, 255)
NICK_COLOR = (140, 146, 158, 255)
FALLBACK_BUBBLE = (96, 126, 201, 235)
FALLBACK_TEXT = (255, 255, 255, 255)


def load_font(size: int) -> Any:
    """按候选顺序加载一个能显示中文的字体。"""
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def parse_color(value: Any, default: Tuple[int, int, int, int] = FALLBACK_TEXT) -> Tuple[int, int, int, int]:
    """解析装扮里的 ARGB 颜色，如 ``0xFF2554c1``。"""
    if not isinstance(value, str):
        return default
    raw = value.strip()
    if raw.lower().startswith("0x"):
        raw = raw[2:]
    if len(raw) == 8:  # AARRGGBB
        try:
            a = int(raw[0:2], 16)
            r = int(raw[2:4], 16)
            g = int(raw[4:6], 16)
            b = int(raw[6:8], 16)
        except ValueError:
            return default
        return (r, g, b, a)
    if len(raw) == 6:
        try:
            return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16), 255)
        except ValueError:
            return default
    return default


def char_weight(char: str) -> float:
    """中文/全角按 1 个字宽算，ASCII 半角按 0.5。"""
    if not char:
        return 0.0
    code = ord(char)
    if code < 0x80:
        return 0.5
    return 1.0


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: Any,
    max_width: Optional[int] = None,
    max_chars: Optional[int] = None,
) -> List[str]:
    """折行：给了 ``max_chars`` 就按「中文字符数」硬换行，否则按像素宽度折。

    ``max_chars`` 优先。按字宽加权计数：一个汉字 = 1，ASCII 半角 = 0.5，
    这样 ``15`` 大约等于「15 个汉字」或「30 个英文字母」。
    """
    lines: List[str] = []
    for paragraph in str(text or "").split("\n"):
        if not paragraph:
            lines.append("")
            continue

        current = ""
        weight = 0.0
        for char in paragraph:
            char_weight_value = char_weight(char)
            if max_chars is not None:
                overflow = current and weight + char_weight_value > max_chars
            else:
                limit = max_width if max_width is not None else 10**9
                overflow = current and draw.textlength(current + char, font=font) > limit

            if overflow:
                lines.append(current)
                current = char
                weight = char_weight_value
            else:
                current += char
                weight += char_weight_value
        lines.append(current)

    return lines


def circle_avatar(data: bytes, size: int) -> Image.Image:
    """把头像裁成圆形；失败则返回灰色占位。"""
    try:
        avatar = Image.open(io.BytesIO(data)).convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
    except Exception:  # noqa: BLE001
        avatar = Image.new("RGBA", (size, size), (200, 205, 215, 255))

    mask = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size * 4 - 1, size * 4 - 1), fill=255)
    mask = mask.resize((size, size), Image.Resampling.LANCZOS)

    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(avatar, (0, 0))
    result.putalpha(mask)
    return result


def _slice(slices: Mapping[str, bytes], key: str) -> Optional[Image.Image]:
    """按中文方位或原始英文文件名取一张切片。"""
    label = CORNER_KEYS.get(key)
    raw = slices.get(label) if label else None
    if raw is None:
        stem = SLICE_STEMS.get(key)
        raw = slices.get(stem) if stem else None
    if not raw:
        return None
    try:
        return Image.open(io.BytesIO(raw)).convert("RGBA")
    except Exception:  # noqa: BLE001
        return None


def compose_bubble(slices: Mapping[str, bytes], width: int, height: int) -> Optional[Image.Image]:
    """按九宫格把气泡拉伸到指定尺寸；素材不全时返回 None。"""
    parts = {key: _slice(slices, key) for key in CORNER_KEYS}
    if any(parts[key] is None for key in ("tl", "tr", "bl", "br")):
        return None

    tl, tr, bl, br = parts["tl"], parts["tr"], parts["bl"], parts["br"]
    assert tl and tr and bl and br

    width = max(width, tl.width + tr.width + 1)
    height = max(height, tl.height + bl.height + 1)
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    inner_w = width - tl.width - tr.width
    inner_h = height - tl.height - bl.height

    center = parts["ct"]
    if center:
        canvas.alpha_composite(center.resize((inner_w, inner_h), Image.Resampling.NEAREST), (tl.width, tl.height))

    for key, size, pos in (
        ("tm", (inner_w, parts["tm"].height if parts["tm"] else 2), (tl.width, 0)),
        ("bm", (inner_w, parts["bm"].height if parts["bm"] else 2), (bl.width, height - (parts["bm"].height if parts["bm"] else 2))),
        ("lm", ((parts["lm"].width if parts["lm"] else 2), inner_h), (0, tl.height)),
        ("rm", ((parts["rm"].width if parts["rm"] else 2), inner_h), (width - (parts["rm"].width if parts["rm"] else 2), tl.height)),
    ):
        image = parts[key]
        if image is None:
            continue
        canvas.alpha_composite(image.resize(size, Image.Resampling.NEAREST), pos)

    canvas.alpha_composite(tl, (0, 0))
    canvas.alpha_composite(tr, (width - tr.width, 0))
    canvas.alpha_composite(bl, (0, height - bl.height))
    canvas.alpha_composite(br, (width - br.width, height - br.height))
    return canvas


def render_card(
    text: str,
    nickname: str = "",
    slices: Optional[Mapping[str, bytes]] = None,
    avatar_bytes: bytes = b"",
    text_color: Tuple[int, int, int, int] = FALLBACK_TEXT,
    bubble_color: Tuple[int, int, int, int] = FALLBACK_BUBBLE,
    font_size: int = 26,
    max_chars_per_line: int = 15,
    mirror: bool = False,
) -> bytes:
    """渲染一张聊天卡片，返回 PNG 字节。"""
    body = str(text or "").strip() or "（无可渲染的文字内容）"
    font = load_font(font_size)
    nick_font = load_font(max(14, font_size - 9))

    measure = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    # 按「多少个中文字符」硬换行（默认 15），不再靠像素宽度猜
    lines = wrap_text(measure, body, font, max_chars=max_chars_per_line)

    line_height = int(font_size * 1.45)
    text_width = max((int(measure.textlength(line, font=font)) for line in lines), default=0)
    text_height = max(line_height * len(lines), line_height)

    # 气泡按行宽撑开，并给一个下限，避免短句看起来挤成一条窄条
    min_text_width = int(font_size * max_chars_per_line * 0.5)
    text_width = max(text_width, min_text_width)

    pad_left, pad_right, pad_y = 52, 34, 22
    bubble_w = text_width + pad_left + pad_right + 12
    bubble_h = text_height + pad_y * 2

    avatar_size = 92
    gap = 16
    margin = 22
    nick_h = int(nick_font.size * 1.6) if nickname else 0

    bubble = compose_bubble(slices or {}, bubble_w, bubble_h)
    if bubble is not None and mirror:
        # 头像在左 = 收到的消息：气泡整体水平翻转，让尾巴朝左
        bubble = bubble.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    actual_h = bubble.height if bubble is not None else bubble_h

    canvas_w = margin * 2 + avatar_size + gap + bubble_w + 24
    canvas_h = margin * 2 + nick_h + max(actual_h, avatar_size)

    canvas = Image.new("RGBA", (canvas_w, canvas_h), BG_COLOR)
    draw = ImageDraw.Draw(canvas)

    avatar = circle_avatar(avatar_bytes, avatar_size)
    canvas.alpha_composite(avatar, (margin, margin + nick_h))

    bubble_x = margin + avatar_size + gap
    bubble_y = margin + nick_h

    if nickname:
        draw.text((bubble_x + 4, margin - 2), nickname, font=nick_font, fill=NICK_COLOR)

    if bubble is not None:
        canvas.alpha_composite(bubble, (bubble_x, bubble_y))
    else:
        draw.rounded_rectangle(
            (bubble_x, bubble_y, bubble_x + bubble_w, bubble_y + bubble_h),
            radius=18,
            fill=bubble_color,
        )

    # 角图比文字高时（九宫格有最小高度），文字按气泡实际高度垂直居中
    text_y = bubble_y + max(pad_y, (actual_h - text_height) // 2)
    # 镜像后装饰跑到右边，文字让位方向也跟着换
    inset_left = (pad_right + 8) if mirror else pad_left
    for index, line in enumerate(lines):
        draw.text((bubble_x + inset_left, text_y + index * line_height), line, font=font, fill=text_color)

    buffer = io.BytesIO()
    canvas.convert("RGB").save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def to_base64_source(png: bytes) -> str:
    """转成 OneBot 图片段可用的内联源（SnowLuma 支持 base64://）。"""
    import base64

    return "base64://" + base64.b64encode(png).decode("ascii")

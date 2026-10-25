"""盘古之白（Pangu spacing）：在中文与拉丁字母／数字之间补一个空格。

设计约束：

- **只做 CJK ↔ 拉丁字母 / 数字**：不碰标点，也不做「中文 ，」这类全角标点规整，
  避免把正文改成模型没写过的东西；
- **幂等**：已经带空格的文本原样返回，连续跑两遍结果一致；
- **保护片段**：小表情 token（``[小表情#187]``）、方括号短词（``[思考]``、``[图片]``）、
  URL、反引号内联代码、``/表情名`` 通道都原样跳过，避免把控制串改坏；
- 纯函数、零依赖，方便单测。
"""

from __future__ import annotations

import re

# 中日韩文字范围：与 pangu.py 保持一致的口径（含扩展 A/B、假名、注音等）。
CJK_CHARS = (
    "\u2e80-\u2eff"  # CJK 部首补充
    "\u2f00-\u2fdf"  # 康熙部首
    "\u3040-\u309f"  # 平假名
    "\u30a0-\u30fa"  # 片假名
    "\u30fc-\u30ff"  # 片假名长音、拗音
    "\u3100-\u312f"  # 注音
    "\u3200-\u32ff"  # 带圈 CJK
    "\u3400-\u4dbf"  # CJK 扩展 A
    "\u4e00-\u9fff"  # CJK 基本区
    "\uf900-\ufaff"  # CJK 兼容表意
)

# 受保护片段：控制串与「不该被插入空格」的正文。
_PROTECTED = re.compile(
    r"("
    r"\[小表情#[^\]\n]*\]"  # 出站小表情 token
    r"|\[[^\[\]\n]{1,6}\]"  # 方括号短词：表情名 / [图片] / [注] 等
    r"|https?://[^\s]+"  # URL
    r"|`[^`\n]*`"  # 反引号内联代码
    r"|/[\u4e00-\u9fff]{1,6}"  # /表情名 通道
    r")"
)

_CJK_LATIN = re.compile(rf"([{CJK_CHARS}])([A-Za-z])")
_LATIN_CJK = re.compile(rf"([A-Za-z])([{CJK_CHARS}])")
_CJK_DIGIT = re.compile(rf"([{CJK_CHARS}])(\d)")
_DIGIT_CJK = re.compile(rf"(\d)([{CJK_CHARS}])")
_MULTI_SPACE = re.compile(r" {2,}")


def apply_pangu_spacing(text: str, *, spacing_digits: bool = True) -> str:
    """给中文与拉丁字母／数字之间补空格。

    Args:
        text: 待处理文本。
        spacing_digits: 是否同时处理「中文 ↔ 阿拉伯数字」；``False`` 时只处理字母。

    Returns:
        str: 处理后的文本；不需要改动时返回原对象内容（等值）。
    """

    if not text:
        return text

    pieces = []
    cursor = 0
    for match in _PROTECTED.finditer(text):
        pieces.append((False, text[cursor:match.start()]))
        pieces.append((True, match.group(0)))
        cursor = match.end()
    pieces.append((False, text[cursor:]))

    if not any(chunk for protected, chunk in pieces if not protected):
        return text

    output = []
    for protected, chunk in pieces:
        if protected or not chunk:
            output.append(chunk)
            continue
        output.append(_spacing_enabled_text(chunk, spacing_digits=spacing_digits))
    return "".join(output)


def _spacing_enabled_text(text: str, *, spacing_digits: bool) -> str:
    """对单个不受保护的片段执行替换（跑两遍保证边界稳定）。"""

    result = text
    for _ in range(2):
        result = _CJK_LATIN.sub(r"\1 \2", result)
        result = _LATIN_CJK.sub(r"\1 \2", result)
        if spacing_digits:
            result = _CJK_DIGIT.sub(r"\1 \2", result)
            result = _DIGIT_CJK.sub(r"\1 \2", result)
        result = _MULTI_SPACE.sub(" ", result)
    return result

"""聊天语感处理：去掉正文结尾的句号与冒号。

聊天场景里「好的。」「我总结一下：」这种落脚很生硬，语音助手式的正式感会盖过口语感。
这里只做一件很窄的事：**整条消息最后一个文本段末尾若只有 1 个 ``。`` / ``：``，就删掉它**。

刻意不做的：

- 连续标点不动（``真的。。。``、``好吧。。``）—— 连敲多个标点是刻意的语气强调，删掉反而失真；
- 不动句中的标点（``第一。第二`` 原样保留）；
- 不动 ``？`` ``！`` ``…`` 这类带情绪的落脚；
- 删成空串时保留原文，避免发出空消息。
"""

from __future__ import annotations

#: 需要从结尾清理的标点（全角句号、全角/半角冒号）。
CHAT_TRAILING_CHARS = "。：:"


def strip_trailing_chat_punctuation(
    text: str,
    *,
    chars: str = CHAT_TRAILING_CHARS,
) -> str:
    """删除文本结尾单个聊天标点。

    只有结尾恰好是 1 个待清标点时才删除；连续 2 个及以上视为刻意强调，原样保留。

    Args:
        text: 待处理文本。
        chars: 视为「结尾标点」的字符集合。

    Returns:
        str: 处理后的文本；无需处理时只去掉结尾空白。
    """

    if not text:
        return text

    stripped = text.rstrip()
    if not stripped:
        return text

    run = len(stripped) - len(stripped.rstrip(chars))
    if run != 1:
        return stripped

    return stripped[:-1].rstrip() or text

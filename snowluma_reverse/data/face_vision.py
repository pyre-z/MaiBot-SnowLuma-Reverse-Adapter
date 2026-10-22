"""QQ 表情视觉描述表的读取门面。

底层是 :class:`~snowluma_reverse.media.face_vision_store.FaceVisionStore`：
包内置表（`scripts/build_face_vision.py` 离线全量生成，随仓库走）
+ 运行时补写层（遇到新表情时由 worker 调默认 VLM 补写，落插件数据目录）。

缺表或条目缺失时返回 ``None``，调用方自然回退到 emoji / 中文名，不影响收发。
"""

from __future__ import annotations

from ..media.face_vision_store import STORE


def describe_face(face_id: str) -> str | None:
    """返回 ``（QQ表情·幽灵｜白色圆润的小幽灵上下漂浮眨眼…）`` 形式的文本。

    Args:
        face_id: QQ 表情 ID（数字 ID 或 Unicode 表情字符）。

    Returns:
        str | None: 有描述时返回渲染好的文本，否则 ``None``（由调用方回退）。
    """
    return STORE.describe(face_id)


def has_face(face_id: str) -> bool:
    """该表情是否已有可用描述。"""
    return STORE.has(face_id)

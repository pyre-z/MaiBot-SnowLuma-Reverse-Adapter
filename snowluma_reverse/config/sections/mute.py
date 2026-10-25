from __future__ import annotations

from typing import Any, ClassVar, Dict, List

from maibot_sdk import Field, PluginConfigBase
from pydantic import ValidationInfo, field_validator

from ..base import _normalize_positive_int

class QQMuteConfig(PluginConfigBase):
    """智能禁言工具的约束配置。"""

    __ui_label__: ClassVar[str] = "禁言工具"
    __ui_order__: ClassVar[int] = 6

    admin_users: List[str] = Field(
        default_factory=list,
        description="禁言保护名单，名单内的用户不会被禁言。",
        json_schema_extra={
            "hint": "每项一个 QQ 号，支持 qq:123456 或 123456 两种写法；群主和管理员始终受保护。",
            "label": "禁言保护名单",
            "order": 0,
        },
    )
    allowed_groups: List[str] = Field(
        default_factory=list,
        description="允许禁言的群白名单，空列表表示不限制。",
        json_schema_extra={
            "hint": "每项一个群号，支持 qq:123456 或 123456 两种写法；空列表表示所有群可用。",
            "label": "禁言群白名单",
            "order": 1,
        },
    )
    min_duration: int = Field(
        default=60,
        description="最短禁言时长，单位秒。",
        json_schema_extra={
            "hint": "模型给出的禁言时长低于该值时会被抬升到该值。",
            "label": "最短时长（秒）",
            "order": 2,
        },
    )
    max_duration: int = Field(
        default=2592000,
        description="最长禁言时长，单位秒。",
        json_schema_extra={
            "hint": "模型给出的禁言时长超过该值时会被截断到该值，默认 30 天。",
            "label": "最长时长（秒）",
            "order": 3,
        },
    )

    @field_validator("admin_users", "allowed_groups", mode="before")
    @classmethod
    def _normalize_scoped_id_lists(cls, value: Any) -> List[str]:
        """规范化带平台前缀的 ID 列表，去除空白与重复项。"""
        if not isinstance(value, list):
            return []
        normalized_values: List[str] = []
        seen_values = set()
        for item in value:
            item_text = str(item).strip()
            if not item_text or item_text in seen_values:
                continue
            seen_values.add(item_text)
            normalized_values.append(item_text)
        return normalized_values

    @field_validator("min_duration", "max_duration", mode="before")
    @classmethod
    def _normalize_positive_duration_fields(cls, value: Any, info: ValidationInfo) -> int:
        """规范化正整数时长字段。"""
        defaults: Dict[str, int] = {"min_duration": 60, "max_duration": 2592000}
        return _normalize_positive_int(value, defaults[str(info.field_name)])

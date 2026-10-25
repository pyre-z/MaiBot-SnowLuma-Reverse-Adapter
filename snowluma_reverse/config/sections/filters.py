from __future__ import annotations

import logging
from typing import Any, ClassVar, List, Literal

from maibot_sdk import Field, PluginConfigBase
from pydantic import field_validator

from ..base import _normalize_string, _normalize_string_list, _schema_i18n

LOGGER = logging.getLogger("snowluma_adapter.config")

class QQFilterConfig(PluginConfigBase):
    """消息过滤配置。"""

    __ui_label__: ClassVar[str] = "消息过滤"
    __ui_order__: ClassVar[int] = 3

    ban_user_id: List[str] = Field(
        default_factory=list,
        description="用户黑名单，拦截指定 QQ 用户的群聊和私聊消息。",
        json_schema_extra={
            "label": "用户黑名单",
            "hint": "每项填写一个 QQ 号；消息在解析前丢弃，不传入麦麦。空列表表示不屏蔽。",
            "order": 6,
            "i18n": _schema_i18n(
                label_en="User blacklist",
                label_ja="ユーザーブラックリスト",
                hint_en="One QQ ID per entry. Group and private messages are dropped before parsing. Empty means no blocking.",
                hint_ja="各項目に QQ 番号を入力します。対象ユーザーのグループ・個人メッセージを解析前に破棄します。空の場合はブロックしません。",
            ),
        },
    )
    ban_qq_bot: bool = Field(
        default=False,
        description="是否屏蔽 QQ 官方机器人消息。",
        json_schema_extra={
            "hint": "开启后会忽略来自 QQ 官方机器人或频道机器人的消息。",
            "i18n": _schema_i18n(
                label_en="Block official bots",
                label_ja="公式 Bot をブロック",
                hint_en="When enabled, messages from QQ official bots or channel bots are ignored.",
                hint_ja="有効にすると、QQ 公式 Bot またはチャンネル Bot からのメッセージを無視します。",
            ),
            "label": "屏蔽官方机器人",
            "order": 5,
        },
    )
    regex_filter_enabled: bool = Field(
        default=False,
        description="是否启用正则表达式消息过滤。",
        json_schema_extra={
            "hint": "开启后将根据正则表达式规则过滤入站消息。",
            "label": "启用正则过滤",
            "order": 1,
        },
    )
    regex_filter_mode: Literal["blacklist", "whitelist"] = Field(
        default="blacklist",
        description="正则过滤模式。blacklist 匹配则丢弃，whitelist 仅放行匹配的消息。",
        json_schema_extra={
            "hint": "黑名单模式下匹配正则的消息会被丢弃；白名单模式下仅匹配正则的消息会被放行。",
            "label": "正则过滤模式",
            "order": 2,
        },
    )
    regex_filter_patterns: List[str] = Field(
        default_factory=list,
        description="正则表达式列表，支持 Python re 模块语法。",
        json_schema_extra={
            "hint": "每条规则为一个 Python 正则表达式，消息文本将逐条匹配。无效的正则表达式会在启动时记录警告并跳过。",
            "label": "正则表达式列表",
            "order": 3,
            "placeholder": r"例如：^广告.*|spam",
        },
    )
    regex_filter_show_dropped: bool = Field(
        default=False,
        description="是否显示未通过正则过滤而被丢弃的消息日志。",
        json_schema_extra={
            "hint": "关闭后不会记录因正则过滤而被丢弃的日志，默认关闭以减少刷屏。",
            "label": "显示正则过滤丢弃日志",
            "order": 4,
        },
    )

    @field_validator("ban_user_id", mode="before")
    @classmethod
    def _normalize_ban_user_id(cls, value: Any) -> List[str]:
        """接受整数或字符串 QQ 号列表，校验后统一为字符串并去重。"""
        if not isinstance(value, list):
            raise ValueError("ban_user_id 必须是 QQ 号列表")
        user_ids: List[str] = []
        for item in value:
            text = str(item).strip()
            if not isinstance(item, (int, str)) or not text.isascii() or not text.isdecimal() or int(text) <= 0:
                raise ValueError("ban_user_id 中的 QQ 号必须是正整数")
            user_id = str(int(text))
            if user_id not in user_ids:
                user_ids.append(user_id)
        return user_ids

    @field_validator("regex_filter_mode", mode="before")
    @classmethod
    def _normalize_regex_filter_mode(cls, value: Any) -> Literal["whitelist", "blacklist"]:
        """规范化正则过滤模式字段。"""
        normalized_value = _normalize_string(value)
        if normalized_value == "whitelist":
            return "whitelist"
        if normalized_value not in ("whitelist", "blacklist"):
            LOGGER.warning(f"无效的 regex_filter_mode 值 '{value}'，已回退到 'blacklist'")
        return "blacklist"

    @field_validator("regex_filter_patterns", mode="before")
    @classmethod
    def _normalize_regex_filter_patterns(cls, value: Any) -> List[str]:
        """规范化正则表达式列表字段。"""
        return _normalize_string_list(value)


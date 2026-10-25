from __future__ import annotations

from typing import ClassVar

from maibot_sdk import Field, PluginConfigBase

from ..base import _schema_i18n

class QQDebugConfig(PluginConfigBase):
    """消息调试配置，各开关默认关闭。"""

    __ui_label__: ClassVar[str] = "调试"
    __ui_order__: ClassVar[int] = 5

    enable_ada_debug_raw_message_log: bool = Field(
        default=False,
        description="调试模式：记录入站原始消息段。",
        json_schema_extra={
            "label": "显示原始消息段",
            "hint": "仅排查消息段结构问题时开启；开启后会记录每条入站消息的原始 message 字段。",
            "i18n": _schema_i18n(
                label_en="Raw inbound debug",
                label_ja="生メッセージデバッグ",
                hint_en="Enable only while debugging segment structure; logs each inbound raw message field at info level.",
                hint_ja="セグメント構造を調査するときだけ有効にしてください。入站 message フィールドを info レベルで記録します。",
            ),
            "order": 0,
        },
    )
    enable_ada_debug_raw_outbound_message_log: bool = Field(
        default=False,
        description="调试模式：记录出站原始发送段。",
        json_schema_extra={
            "label": "显示原始发送段",
            "hint": "仅排查发送消息段结构问题时开启；开启后会记录每条出站消息实际调用的 action 和 params。",
            "i18n": _schema_i18n(
                label_en="Raw outbound debug",
                label_ja="生送信デバッグ",
                hint_en=(
                    "Enable only while debugging outbound segment structure; logs the action and params "
                    "actually sent for each outbound message."
                ),
                hint_ja=(
                    "送信セグメント構造を調査するときだけ有効にしてください。"
                    "各送信メッセージで実際に渡す action と params を記録します。"
                ),
            ),
            "order": 1,
        },
    )

    ignore_self_message: bool = Field(
        default=False,
        description="是否忽略机器人自身发送的消息。",
        json_schema_extra={
            "hint": "开启后会忽略机器人自身发送的消息。",
            "i18n": _schema_i18n(
                label_en="Ignore self messages",
                label_ja="自身のメッセージを無視",
                hint_en="When enabled, messages sent by the bot itself are ignored.",
                hint_ja="有効にすると、Bot 自身が送信したメッセージを無視します。",
            ),
            "label": "忽略自身消息",
            "order": 2,
        },
    )


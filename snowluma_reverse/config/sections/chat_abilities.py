from __future__ import annotations

from typing import ClassVar

from maibot_sdk import Field, PluginConfigBase

from ..base import _schema_i18n

class QQChatAbilitiesConfig(PluginConfigBase):
    """聊天能力（LLM 工具）开关配置。"""

    __ui_label__: ClassVar[str] = "聊天能力"
    __ui_order__: ClassVar[int] = 1

    enable_private_chat_tool: bool = Field(
        default=False,
        description="是否启用主动开启私聊工具。",
        json_schema_extra={
            "hint": "开启后，模型可向指定 QQ 用户发送首条私聊消息；请在宿主适配器策略中放行该私聊。",
            "i18n": _schema_i18n(
                label_en="Enable private chat tool",
                label_ja="個人チャット開始ツールを有効化",
                hint_en=(
                    "When enabled, the model can send the first private message to a user; "
                    "grant the chat in the host adapter policy."
                ),
                hint_ja=(
                    "有効にすると、モデルは指定ユーザーへ最初の個人メッセージを送信できます；"
                    "ホスト側のアダプターポリシーでその個人チャットを許可してください。"
                ),
            ),
            "label": "启用主动私聊工具",
            "order": 0,
        },
    )
    enable_poke_tool: bool = Field(
        default=False,
        description="是否启用戳一戳工具。",
        json_schema_extra={
            "hint": "开启后，模型可向指定 QQ 用户发送戳一戳；群聊中戳当前群成员，私聊中发送好友戳一戳。",
            "i18n": _schema_i18n(
                label_en="Enable poke tool",
                label_ja="poke ツールを有効化",
                hint_en=(
                    "When enabled, the model can poke a QQ user; in group chats the current group is used, "
                    "in private chats a friend poke is sent."
                ),
                hint_ja=(
                    "有効にすると、モデルは指定ユーザーに poke を送信できます；"
                    "グループチャットでは現在のグループ、個人チャットでは友達への poke を送信します。"
                ),
            ),
            "label": "启用戳一戳工具",
            "order": 1,
        },
    )
    enable_recall_tool: bool = Field(
        default=False,
        description="是否启用消息撤回工具。",
        json_schema_extra={
            "hint": "开启后，模型可撤回消息；撤回自己的消息限 2 分钟内，撤回他人消息需要机器人是群管理员。",
            "i18n": _schema_i18n(
                label_en="Enable recall tool",
                label_ja="メッセージ撤回ツールを有効化",
                hint_en=(
                    "When enabled, the model can recall messages; own messages within 2 minutes, "
                    "others' messages require the bot to be a group admin."
                ),
                hint_ja=(
                    "有効にすると、モデルはメッセージを撤回できます；"
                    "自身のメッセージは 2 分以内、他人のメッセージは Bot がグループ管理者である必要があります。"
                ),
            ),
            "label": "启用消息撤回工具",
            "order": 2,
        },
    )
    enable_mute_tool: bool = Field(
        default=False,
        description="是否启用智能禁言工具。",
        json_schema_extra={
            "hint": "开启后，模型可根据消息 ID 禁言发送者；群主、管理员及保护名单中的用户不会被禁言，"
            "可通过 [mute] 节限制生效群与时长范围。",
            "i18n": _schema_i18n(
                label_en="Enable mute tool",
                label_ja="ミュートツールを有効化",
                hint_en=(
                    "When enabled, the model can mute the sender of a message by its ID; "
                    "group owners, admins and protected users are never muted. "
                    "Scope groups and duration limits in the [mute] section."
                ),
                hint_ja=(
                    "有効にすると、モデルはメッセージ ID で送信者をミュートできます；"
                    "グループのオーナー・管理者・保護リストのユーザーはミュートされません。"
                    "対象グループと時間の範囲は [mute] セクションで制限できます。"
                ),
            ),
            "label": "启用智能禁言工具",
            "order": 3,
        },
    )
    enable_emoji_like_tool: bool = Field(
        default=False,
        description="是否启用表情表态工具。",
        json_schema_extra={
            "hint": "开启后，模型可给消息贴表情回应（如赞、爱心）。",
            "i18n": _schema_i18n(
                label_en="Enable emoji reaction tool",
                label_ja="絵文字リアクションツールを有効化",
                hint_en="When enabled, the model can react to a message with a QQ emoji (e.g. thumbs up, heart).",
                hint_ja="有効にすると、モデルはメッセージに QQ 絵文字（いいね・ハートなど）でリアクションできます。",
            ),
            "label": "启用表情表态工具",
            "order": 4,
        },
    )
    enable_forward_tool: bool = Field(
        default=False,
        description="是否启用消息转发工具。",
        json_schema_extra={
            "hint": "开启后，模型可把一批消息打包成合并转发，发送到指定群或私聊。",
            "i18n": _schema_i18n(
                label_en="Enable forward tool",
                label_ja="転送ツールを有効化",
                hint_en=(
                    "When enabled, the model can bundle messages into a merged forward "
                    "and send it to a specific group or private chat."
                ),
                hint_ja=(
                    "有効にすると、モデルはメッセージをまとめて転送し、"
                    "指定したグループまたは個人チャットへ送信できます。"
                ),
            ),
            "label": "启用消息转发工具",
            "order": 5,
        },
    )


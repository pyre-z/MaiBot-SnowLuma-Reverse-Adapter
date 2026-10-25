from __future__ import annotations

from typing import ClassVar

from maibot_sdk import Field, PluginConfigBase

from ..base import _notice_field, _schema_i18n

class QQNoticeConfig(PluginConfigBase):
    """通知事件传递配置。

    采用白名单式开关：仅明确启用的通知类型会注入 Host，
    未在此处列出的通知类型（如输入状态 notify.input_status）默认丢弃。
    """

    __ui_label__: ClassVar[str] = "通知事件"
    __ui_order__: ClassVar[int] = 4

    enabled: bool = Field(
        default=True,
        description="是否将适配器推送的通知事件转发给 Host。",
        json_schema_extra={
            "hint": "关闭后，戳一戳、禁言、撤回、入群退群等所有通知事件都不会传入 Host。",
            "i18n": _schema_i18n(
                label_en="Enable notice events",
                label_ja="通知イベントを有効化",
                hint_en="When disabled, poke, ban, recall, member change and all other notice events are not routed to the Host.",
                hint_ja="無効にすると、poke、禁言、撤回、メンバー変更などすべての通知イベントは Host に転送されません。",
            ),
            "label": "启用通知事件",
            "order": 0,
        },
    )
    enable_poke: bool = _notice_field(
        label="传递戳一戳",
        description="是否传递戳一戳通知。",
        order=1,
        label_en="Route poke",
        label_ja="poke を転送",
    )
    enable_friend_recall: bool = _notice_field(
        label="传递好友撤回",
        description="是否传递好友消息撤回通知。",
        order=2,
        label_en="Route friend recall",
        label_ja="友達の撤回を転送",
    )
    enable_group_recall: bool = _notice_field(
        label="传递群消息撤回",
        description="是否传递群消息撤回通知。",
        order=3,
        label_en="Route group recall",
        label_ja="グループ撤回を転送",
    )
    enable_group_ban: bool = _notice_field(
        label="传递禁言",
        description="是否传递群禁言和解除禁言通知。",
        order=4,
        label_en="Route group ban",
        label_ja="グループ禁言を転送",
    )
    enable_group_msg_emoji_like: bool = _notice_field(
        label="传递消息表情回应",
        description="是否传递群消息表情回应通知。",
        order=5,
        label_en="Route emoji reactions",
        label_ja="絵文字リアクションを転送",
    )
    enable_group_upload: bool = _notice_field(
        label="传递群文件上传",
        description="是否传递群文件上传通知。",
        order=6,
        label_en="Route group uploads",
        label_ja="グループファイルを転送",
    )
    enable_group_increase: bool = _notice_field(
        label="传递入群",
        description="是否传递群成员增加通知。",
        order=7,
        label_en="Route member joins",
        label_ja="参加通知を転送",
    )
    enable_group_decrease: bool = _notice_field(
        label="传递退群",
        description="是否传递群成员减少通知。",
        order=8,
        label_en="Route member leaves",
        label_ja="退出通知を転送",
    )
    enable_group_admin: bool = _notice_field(
        label="传递管理员变动",
        description="是否传递群管理员变动通知。",
        order=9,
        label_en="Route admin changes",
        label_ja="管理者変更を転送",
    )
    enable_essence: bool = _notice_field(
        label="传递精华消息",
        description="是否传递精华消息变动通知。",
        order=10,
        label_en="Route essence changes",
        label_ja="精華メッセージを転送",
    )
    enable_friend_add: bool = _notice_field(
        label="传递新好友", description="是否传递新好友通知。", order=12,
        label_en="Route friend additions", label_ja="友達追加を転送",
    )
    enable_group_card: bool = _notice_field(
        label="传递群名片变更", description="是否传递群名片变更通知。", order=13,
        label_en="Route group card changes", label_ja="グループカード変更を転送",
    )
    forward_input_status: bool = Field(
        default=False, description="是否转发对方正在输入状态。",
        json_schema_extra={
            "label": "转发输入状态", "hint": "开启后会将 notify.input_status 转发为普通通知。",
            "i18n": _schema_i18n(label_en="Forward input status", label_ja="入力状態を転送"),
            "order": 14,
        },
    )
    enable_group_name: bool = _notice_field(
        label="传递群名变更",
        description="是否传递群名称变更通知。",
        order=11,
        label_en="Route group name changes",
        label_ja="グループ名変更を転送",
    )


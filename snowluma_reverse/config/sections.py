"""Typed configuration sections, preserving the established UI schema."""

from __future__ import annotations

import logging
from typing import Any, ClassVar, Dict, List, Literal

from maibot_sdk import Field, PluginConfigBase
from pydantic import ValidationInfo, field_validator

from .base import _normalize_positive_float, _normalize_positive_int, _normalize_string, _normalize_string_list, _schema_i18n, _notice_field
from ..constants import (
    DEFAULT_ACTION_TIMEOUT_SEC, DEFAULT_HEARTBEAT_INTERVAL_SEC, DEFAULT_MAX_MESSAGE_SIZE,
    DEFAULT_SERVER_LISTEN_HOST, DEFAULT_SERVER_LISTEN_PATH, DEFAULT_SERVER_LISTEN_PORT,
    SUPPORTED_CONFIG_VERSION,
)

LOGGER = logging.getLogger("snowluma_adapter.config")
CLIENT_TYPE_VALUES = Literal["auto", "napcat", "snowluma"]

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


class QQPluginOptions(PluginConfigBase):
    """插件级配置。"""

    __ui_label__: ClassVar[str] = "插件设置"
    __ui_order__: ClassVar[int] = 0

    enabled: bool = Field(
        default=False,
        description="是否启用适配器。",
        json_schema_extra={
            "hint": "关闭后插件会保持空闲，不会主动建立 WebSocket 连接。",
            "i18n": _schema_i18n(
                label_en="Enable adapter",
                label_ja="アダプターを有効化",
                hint_en="When disabled, the plugin stays idle and will not open a WebSocket connection.",
                hint_ja="無効にすると、プラグインは待機状態のままになり、WebSocket 接続を開始しません。",
            ),
            "label": "启用适配器",
            "order": 0,
        },
    )
    qq_face_parse_mode: Literal["description", "emoji"] = Field(
        default="description",
        description="QQ 自带表情解析模式：中文描述锚点 / 近似 Unicode emoji。",
        json_schema_extra={
            "label": "QQ表情解析模式",
            "hint": (
                "[description] 输出 `[小表情·幽灵#187]` 锚点，装 `emoticon-vision` 插件后会被替换成"
                " `[小表情·幽灵：外观描述|情绪|情绪]`；未装插件时保持锚点，模型也知道这是哪个表情。"
                "[emoji] 能对上时用 Unicode emoji，否则回退同样的锚点。"
            ),
            "i18n": _schema_i18n(
                label_en="QQ face parsing",
                label_ja="QQ 標準顔文字の解析",
                hint_en=(
                    "[description] emits a [小表情·name#id] anchor that the emoticon-vision plugin "
                    "expands into a visual description; [emoji] prefers an approximate Unicode emoji."
                ),
                hint_ja=(
                    "[description] は [小表情·名称#ID] アンカーを出力し、emoticon-vision プラグインが"
                    "外観説明に展開します；[emoji] は近い Unicode 絵文字を優先します。"
                ),
            ),
            "order": 1,
        },
    )
    enable_text_face_conversion: bool = Field(
        default=False,
        description="发送时将 /表情名 格式的文本转换为 QQ 原生表情，未知名称保持原样。",
        json_schema_extra={
            "label": "启用文本转QQ表情",
            "hint": "开启后，/捂脸 /微笑 等已知名称会转换为 QQ 表情；找不到的名称不转换。",
            "i18n": _schema_i18n(
                label_en="Convert text to QQ faces",
                label_ja="テキストを QQ 絵文字に変換",
                hint_en="Convert known /face-name text to native QQ faces when sending; unknown names stay unchanged.",
                hint_ja="送信時に既知の /表情名 を QQ 絵文字に変換します。不明な名前はそのまま送信します。",
            ),
            "order": 2,
        },
    )
    enable_text_face_token: bool = Field(
        default=True,
        description="发送时将 [小表情#ID] 文本转换为 QQ 原生小表情，未收录的 ID 保持原样。",
        json_schema_extra={
            "label": "启用小表情 token",
            "hint": "emoticon-vision 插件挑表情时会返回 [小表情#187] 这类 token；"
            "模型原样写进回复即可变成原生表情。只有数字且已收录的 ID 会被转换。",
            "i18n": _schema_i18n(
                label_en="Enable emoticon token",
                label_ja="小表情トークンを有効化",
                hint_en="Convert [小表情#187] tokens from the emoticon-vision plugin into native QQ faces; "
                "unknown or non-numeric IDs stay as plain text.",
                hint_ja="emoticon-vision が返す [小表情#187] 形式を QQ 絵文字に変換します；"
                "未収録・非数字の ID はそのまま送信します。",
            ),
            "order": 3,
        },
    )
    enable_text_face_name_token: bool = Field(
        default=True,
        description="发送时将 [汗]、[吃瓜] 这类表情名文本转换为 QQ 原生小表情，表情表里没有的名字保持原样。",
        json_schema_extra={
            "label": "启用表情名兜底",
            "hint": "模型有时会把 QQ 表情写成 [汗]、[吃瓜] 这类旧样式；开启后只转换表情表里存在的名字，"
            "[图片]、[注] 等普通方括号内容不受影响。",
            "i18n": _schema_i18n(
                label_en="Enable face-name fallback",
                label_ja="表情名フォールバックを有効化",
                hint_en="Convert legacy [汗]/[吃瓜]-style names that exist in the face table into native QQ faces; "
                "other bracketed text such as [图片] stays unchanged.",
                hint_ja="旧式の [汗]/[吃瓜] など表情表にある名前を QQ 絵文字に変換します；"
                "[图片] など他の括弧書きはそのまま送信します。",
            ),
            "order": 4,
        },
    )
    enable_text_at_conversion: bool = Field(
        default=False,
        description="将群聊发送文本中的 @QQ号、@群名片或 @昵称转换为实际 @。真实 @ 的相邻去重始终生效。",
        json_schema_extra={
            "label": "启用文本转@",
            "hint": "仅转换能唯一匹配当前群成员的完整名称；未知或重名保留原文，相邻同目标 @ 合并。",
            "i18n": _schema_i18n(
                label_en="Convert text mentions",
                label_ja="テキストのメンションを変換",
                hint_en="Resolve full QQ IDs, group cards or nicknames within the current group; "
                "keep unknown or ambiguous names and merge adjacent mentions of the same user.",
                hint_ja="現在のグループ内で QQ 番号・グループ名・ニックネームを完全一致で検索します。"
                "不明・同名はそのままにし、隣接する同じユーザーへのメンションを統合します。",
            ),
            "order": 5,
        },
    )
    enable_pangu_spacing: bool = Field(
        default=True,
        description="发送前在中文与英文/数字之间补一个空格（盘古之白），不碰标点、不重复加空格。",
        json_schema_extra={
            "label": "盘古之白",
            "hint": "「这是Flash吧」会变成「这是 Flash 吧」；小表情 token、URL、反引号代码保持原样，已带空格的不会再加。",
            "i18n": _schema_i18n(
                label_en="Pangu spacing",
                label_ja="パングー・スペース",
                hint_en="Insert a space between CJK and Latin/digit text before sending; "
                "face tokens, URLs and inline code stay untouched, already-spaced text is idempotent.",
                hint_ja="送信前に中国語と英数字の間に半角スペースを入れます；"
                "小表情トークン・URL・インラインコードは変更せず、既存のスペースは増やしません。",
            ),
            "order": 6,
        },
    )
    enable_pangu_spacing_digits: bool = Field(
        default=True,
        description="盘古之白是否也处理中文与阿拉伯数字之间（「5个人」→「5 个人」）。",
        json_schema_extra={
            "label": "数字也加空格",
            "hint": "关闭后只处理中文与英文字母之间，数字紧贴中文时保持原样。仅在开启「盘古之白」时生效。",
            "i18n": _schema_i18n(
                label_en="Space around digits",
                label_ja="数字にもスペース",
                hint_en="Also space CJK against Arabic numerals; turn off to only space Latin letters. "
                "Only effective when Pangu spacing is on.",
                hint_ja="中国語と半角数字の間にもスペースを入れます；オフにすると英字のみ対象。"
                "「パングー・スペース」が有効なときのみ作用します。",
            ),
            "order": 7,
        },
    )
    enable_private_at_strip: bool = Field(
        default=True,
        description="私聊发送前剥离 at 段：QQ 拒收私聊里的 at 元素，不剥离会导致整条消息发送失败。",
        json_schema_extra={
            "label": "私聊剥离 @ 段",
            "hint": "模型给 reply 带 attach_at 时会产出 at 段，QQ 私聊拒收。保持开启只丢 at、正文照常发出。",
            "i18n": _schema_i18n(
                label_en="Strip mentions in private chats",
                label_ja="個人チャットのメンションを除去",
                hint_en="QQ rejects `at` elements in private messages, which drops the whole message. "
                "Keep this on to strip the mention and still deliver the text.",
                hint_ja="QQ は個人チャットの at 要素を拒否し、メッセージ全体が送信できません。"
                "オンにすると at のみ除去して本文は送信します。",
            ),
            "order": 8,
        },
    )
    client_type: CLIENT_TYPE_VALUES = Field(
        default="auto",
        description="对端客户端类型：auto 连接后自动判定，也可固定为 napcat 或 snowluma。",
        json_schema_extra={
            "hint": (
                "auto 在每次连入后用 get_version_info 自动判定对端实现；"
                "固定值仅做一致性校验，与对端不符时按声明值运行并打印告警。"
            ),
            "i18n": _schema_i18n(
                label_en="Peer client type",
                label_ja="対向クライアント種別",
                hint_en=(
                    "auto detects the peer via get_version_info after each connect; "
                    "a fixed value is cross-checked against the detected implementation."
                ),
                hint_ja=(
                    "auto は接続後に get_version_info で対向を判定します；"
                    "固定値の場合は判定結果と一致するか検証します。"
                ),
            ),
            "label": "对端类型",
            "order": 9,
        },
    )

    @field_validator("client_type", mode="before")
    @classmethod
    def _normalize_client_type(cls, value: Any) -> CLIENT_TYPE_VALUES:
        """规范化客户端类型字段。

        Args:
            value: 原始配置值。

        Returns:
            CLIENT_TYPE_VALUES: 合法的客户端类型；非法时回退到 auto。
        """

        normalized_value = _normalize_string(value).lower()
        if normalized_value in {"auto", "napcat", "snowluma"}:
            return normalized_value  # type: ignore[return-value]
        if normalized_value:
            LOGGER.warning(f"无效的 client_type 值 '{value}'，已回退到 'auto'")
        return "auto"
    config_version: str = Field(
        default=SUPPORTED_CONFIG_VERSION,
        description="当前配置结构版本。",
        json_schema_extra={
            "disabled": True,
            "hidden": True,
            "i18n": _schema_i18n(label_en="Config version", label_ja="設定バージョン"),
            "label": "配置版本",
            "order": 99,
        },
    )

    def should_connect(self) -> bool:
        """判断当前配置下是否应当启动连接。

        Returns:
            bool: 若插件连接已启用，则返回 ``True``。
        """

        return self.enabled

    @field_validator("config_version", mode="before")
    @classmethod
    def _normalize_config_version(cls, value: Any) -> str:
        """规范化配置版本字段。

        Args:
            value: 原始配置值。

        Returns:
            str: 去除首尾空白后的配置版本；若为空则回退到当前支持版本。
        """

        normalized_value = _normalize_string(value)
        return normalized_value or SUPPORTED_CONFIG_VERSION


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


class QQReverseServerConfig(PluginConfigBase):
    """反向 WebSocket 服务端配置（适配器监听，SnowLuma 主动连入）。"""

    __ui_label__: ClassVar[str] = "反向服务端"
    __ui_order__: ClassVar[int] = 3

    listen_host: str = Field(
        default=DEFAULT_SERVER_LISTEN_HOST,
        description="反向 WebSocket 监听地址，容器内通常填 0.0.0.0。",
        json_schema_extra={
            "hint": "监听 0.0.0.0 表示接受所有网卡连接；只允许本机反代时可填 127.0.0.1。",
            "i18n": _schema_i18n(
                label_en="Listen address",
                label_ja="待受アドレス",
                hint_en="0.0.0.0 accepts every interface; use 127.0.0.1 when only a local reverse proxy connects.",
                hint_ja="0.0.0.0 は全インターフェースで待ち受けます。ローカル逆プロキシのみの場合は 127.0.0.1。",
            ),
            "label": "监听地址",
            "order": 0,
            "placeholder": DEFAULT_SERVER_LISTEN_HOST,
        },
    )
    listen_port: int = Field(
        default=DEFAULT_SERVER_LISTEN_PORT,
        description="反向 WebSocket 监听端口，需与容器端口映射一致。",
        json_schema_extra={
            "hint": "SnowLuma 侧填写的连接地址端口需与这里保持一致（或经反向代理转发）。",
            "i18n": _schema_i18n(
                label_en="Listen port",
                label_ja="待受ポート",
                hint_en="Must match the container port mapping and the port used by SnowLuma or the reverse proxy.",
                hint_ja="コンテナのポートマッピングおよび SnowLuma / 逆プロキシ側のポートと一致させてください。",
            ),
            "label": "监听端口",
            "order": 1,
            "step": 1,
        },
    )
    listen_path: str = Field(
        default=DEFAULT_SERVER_LISTEN_PATH,
        description="反向 WebSocket 路径，SnowLuma 侧连接地址需带上同一路径。",
        json_schema_extra={
            "hint": "默认 /onebot/v11/ws；反向代理转发时保持该路径不变即可。",
            "i18n": _schema_i18n(
                label_en="Listen path",
                label_ja="待受パス",
                hint_en="Defaults to /onebot/v11/ws; keep the same path in the reverse proxy.",
                hint_ja="既定は /onebot/v11/ws。逆プロキシでも同じパスを使用してください。",
            ),
            "label": "监听路径",
            "order": 2,
            "placeholder": DEFAULT_SERVER_LISTEN_PATH,
        },
    )
    token: str = Field(
        default="",
        description="访问令牌，SnowLuma 侧需配置相同值；与 allowed_ips 至少要设置一项。",
        json_schema_extra={
            "hint": "对端以 Authorization: Bearer 或 ?access_token= 提交；留空时依赖 allowed_ips 限制来源。",
            "i18n": _schema_i18n(
                label_en="Access token",
                label_ja="アクセストークン",
                hint_en="The peer sends Authorization: Bearer or ?access_token=. Leave empty only when allowed_ips restricts sources.",
                hint_ja="対向は Authorization: Bearer または ?access_token= で送信します。空欄の場合は allowed_ips で制限してください。",
                placeholder_en="Optional but recommended",
                placeholder_ja="推奨",
            ),
            "input_type": "password",
            "label": "访问令牌",
            "order": 3,
            "placeholder": "建议填写",
        },
    )
    allowed_ips: List[str] = Field(
        default_factory=list,
        description="允许接入的来源 IP 或 CIDR 列表；留空表示不限制来源。",
        json_schema_extra={
            "hint": "例如 203.0.113.10 或 10.0.0.0/8；对端经反向代理接入时这里看到的是代理地址。",
            "i18n": _schema_i18n(
                label_en="Allowed source IPs",
                label_ja="許可ソース IP",
                hint_en="For example 203.0.113.10 or 10.0.0.0/8. Behind a reverse proxy this sees the proxy address.",
                hint_ja="例：203.0.113.10 や 10.0.0.0/8。逆プロキシ経由の場合はプロキシのアドレスになります。",
            ),
            "label": "来源 IP 白名单",
            "order": 4,
            "placeholder": "留空表示不限制",
        },
    )
    expect_self_id: str = Field(
        default="",
        description="可选：只接受指定 X-Self-ID（机器人 QQ 号）的连接。",
        json_schema_extra={
            "hint": "留空表示接受任意账号；填写后与之不符的连接会被拒绝。",
            "i18n": _schema_i18n(
                label_en="Expected self ID",
                label_ja="期待 self ID",
                hint_en="Empty accepts any account; otherwise connections with a different X-Self-ID are rejected.",
                hint_ja="空欄は任意のアカウントを許可します。異なる X-Self-ID の接続は拒否されます。",
            ),
            "label": "限定机器人账号",
            "order": 5,
            "placeholder": "留空表示不限制",
        },
    )
    heartbeat_interval: float = Field(
        default=DEFAULT_HEARTBEAT_INTERVAL_SEC,
        description="协议层心跳保活间隔，单位为秒。",
        json_schema_extra={
            "hint": "服务端会按该间隔发送 WebSocket ping；必须大于 0。",
            "i18n": _schema_i18n(
                label_en="Heartbeat interval (sec)",
                label_ja="ハートビート間隔（秒）",
                hint_en="The server pings at this interval. Must be greater than 0.",
                hint_ja="この間隔で WebSocket ping を送信します。0 より大きい値にしてください。",
            ),
            "label": "心跳间隔（秒）",
            "order": 6,
            "step": 1,
        },
    )
    action_timeout_sec: float = Field(
        default=DEFAULT_ACTION_TIMEOUT_SEC,
        description="调用 OneBot 动作接口的超时时间，单位为秒。",
        json_schema_extra={
            "hint": "发送消息、查询信息等动作会在超时后报错。",
            "i18n": _schema_i18n(
                label_en="Action timeout (sec)",
                label_ja="アクションタイムアウト（秒）",
                hint_en="Actions such as sending messages or querying info fail after this timeout.",
                hint_ja="メッセージ送信や情報取得などのアクションは、この時間を超えるとエラーになります。",
            ),
            "label": "动作超时（秒）",
            "order": 7,
            "step": 1,
        },
    )
    max_message_size: int = Field(
        default=DEFAULT_MAX_MESSAGE_SIZE,
        description="单条 WebSocket 消息允许的最大字节数。",
        json_schema_extra={
            "hint": "含 base64 图片、语音的消息可能较大；默认 16 MiB。",
            "i18n": _schema_i18n(
                label_en="Max message size (bytes)",
                label_ja="最大メッセージサイズ（バイト）",
                hint_en="Messages carrying base64 images or audio can be large; the default is 16 MiB.",
                hint_ja="base64 画像や音声を含むメッセージは大きくなります。既定は 16 MiB。",
            ),
            "label": "最大消息字节数",
            "order": 8,
        },
    )
    connection_id: str = Field(
        default="",
        description="可选连接标识，用于区分多条适配器链路。",
        json_schema_extra={
            "hint": "当存在多条连接时，可用它作为路由作用域标识。",
            "i18n": _schema_i18n(
                label_en="Connection ID",
                label_ja="接続識別子",
                hint_en="When multiple connections exist, use this as the routing scope identifier.",
                hint_ja="複数の接続がある場合、ルーティングスコープの識別子として使用できます。",
            ),
            "label": "连接标识",
            "order": 9,
            "placeholder": "例如：primary",
        },
    )

    def normalized_path(self) -> str:
        """返回规范化后的监听路径。

        Returns:
            str: 以 ``/`` 开头且非空的路径。
        """

        path = _normalize_string(self.listen_path) or DEFAULT_SERVER_LISTEN_PATH
        if not path.startswith("/"):
            path = f"/{path}"
        return path

    def endpoint_url(self) -> str:
        """返回供 SnowLuma 填写或反向代理转发使用的完整地址。

        Returns:
            str: ``ws://host:port/path`` 形式的地址。
        """

        return f"ws://{self.listen_host}:{self.listen_port}{self.normalized_path()}"

    @field_validator("listen_host", mode="before")
    @classmethod
    def _normalize_listen_host(cls, value: Any) -> str:
        """规范化监听地址字段。

        Args:
            value: 原始配置值。

        Returns:
            str: 去除首尾空白后的监听地址；显式空值由运行时校验拒绝。
        """

        return _normalize_string(value)

    @field_validator("listen_path", mode="before")
    @classmethod
    def _normalize_listen_path(cls, value: Any) -> str:
        """规范化监听路径字段。

        Args:
            value: 原始配置值。

        Returns:
            str: 去除首尾空白后的监听路径；若为空则回退到默认值。
        """

        return _normalize_string(value) or DEFAULT_SERVER_LISTEN_PATH

    @field_validator("listen_port", mode="before")
    @classmethod
    def _normalize_listen_port(cls, value: Any) -> int:
        """规范化监听端口字段。

        Args:
            value: 原始配置值。

        Returns:
            int: 原始端口整数；非法值归零并交由运行时前置校验拒绝。
        """
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @field_validator("allowed_ips", mode="before")
    @classmethod
    def _normalize_allowed_ips(cls, value: Any) -> List[str]:
        """把字符串或列表统一为去空白的 IP 列表。

        Args:
            value: 原始配置值，可为逗号/换行分隔字符串或可迭代对象。

        Returns:
            List[str]: 规范化后的来源 IP 列表。
        """

        if value in (None, ""):
            return []
        if isinstance(value, str):
            raw_items: Any = value.replace("\n", ",").split(",")
        elif isinstance(value, (list, tuple, set)):
            raw_items = value
        else:
            return []
        return [item for item in (_normalize_string(entry) for entry in raw_items) if item]

    @field_validator("token", "expect_self_id", "connection_id", mode="before")
    @classmethod
    def _normalize_text_fields(cls, value: Any) -> str:
        """规范化文本字段。

        Args:
            value: 原始配置值。

        Returns:
            str: 去除首尾空白后的字符串值。
        """

        return _normalize_string(value)

    @field_validator("heartbeat_interval", "action_timeout_sec", mode="before")
    @classmethod
    def _normalize_positive_float_fields(cls, value: Any, info: ValidationInfo) -> float:
        """规范化正浮点数字段。

        Args:
            value: 原始配置值。
            info: Pydantic 字段校验上下文。

        Returns:
            float: 合法的正浮点数；非法时回退到对应默认值。
        """

        default_values: Dict[str, float] = {
            "heartbeat_interval": DEFAULT_HEARTBEAT_INTERVAL_SEC,
            "action_timeout_sec": DEFAULT_ACTION_TIMEOUT_SEC,
        }
        return _normalize_positive_float(value, default_values[str(info.field_name)])


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

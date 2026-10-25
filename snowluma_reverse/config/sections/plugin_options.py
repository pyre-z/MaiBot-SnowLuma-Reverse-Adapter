from __future__ import annotations

import logging
from typing import Any, ClassVar, Literal

from maibot_sdk import Field, PluginConfigBase
from pydantic import field_validator

from ..base import _normalize_string, _schema_i18n
from ...constants import SUPPORTED_CONFIG_VERSION

LOGGER = logging.getLogger("snowluma_adapter.config")
CLIENT_TYPE_VALUES = Literal["auto", "napcat", "snowluma"]

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
    enable_trailing_punctuation_strip: bool = Field(
        default=True,
        description="发送前删掉正文结尾单个「。」或「：」，符合聊天口语；连续标点视为刻意、问号感叹号都不动。",
        json_schema_extra={
            "label": "去掉结尾句号/冒号",
            "hint": "「好的。」→「好的」、「我总结一下：」→「我总结一下」；「真的。。。」这种连续标点保留原样。",
            "i18n": _schema_i18n(
                label_en="Drop trailing period/colon",
                label_ja="文末の句点・コロンを削除",
                hint_en="Strips a single trailing 「。」/「：」; repeated marks like 「。。。」 count as "
                "deliberate emphasis and stay, as do mid-sentence punctuation, 「？」 and 「！」.",
                hint_ja="文末の「。」「：」を1つだけ削除します；「。。。」のような連続記号は意図的な強調として残します。"
                "文中の句読点や「？」「！」も変更しません。",
            ),
            "order": 9,
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
            "order": 10,
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


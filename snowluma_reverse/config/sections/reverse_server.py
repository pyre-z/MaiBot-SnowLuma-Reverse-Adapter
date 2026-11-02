from __future__ import annotations

from typing import Any, ClassVar, Dict, List

from maibot_sdk import Field, PluginConfigBase
from pydantic import ValidationInfo, field_validator

from ..base import _normalize_positive_float, _normalize_string, _schema_i18n
from ...constants import (
    DEFAULT_ACTION_TIMEOUT_SEC,
    DEFAULT_HEARTBEAT_INTERVAL_SEC,
    DEFAULT_MAX_MESSAGE_SIZE,
    DEFAULT_SERVER_LISTEN_HOST,
    DEFAULT_SERVER_LISTEN_PATH,
    DEFAULT_SERVER_LISTEN_PORT,
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

    slot_idle_timeout_sec: float = Field(
        default=300.0,
        description=(
            "空闲槽位回收时间：某条 slot 连接超过该秒数没有被用于发送动作就会被关闭；"
            "事件所在槽位不受影响，0 表示不回收。"
        ),
        json_schema_extra={
            "hint": "多连接分流时，长期没人用的 slot 会自动断开以释放连接；设为 0 可关闭该行为。",
            "i18n": _schema_i18n(
                label_en="Idle slot timeout (sec)",
                label_ja="アイドルスロット回収（秒）",
                hint_en="Slots unused for this long are closed to free connections. The event slot is never recycled. 0 disables it.",
                hint_ja="この秒数使われなかった slot は切断されます。イベント用スロットは対象外です。0 で無効化。",
            ),
            "label": "空闲槽位回收（秒）",
            "order": 10,
            "step": 1,
        },
    )
    max_slots: int = Field(
        default=8,
        description="允许同时存在的最大槽位数量，超出后新连接的 slot 会被拒绝。",
        json_schema_extra={
            "hint": "按 SnowLuma 侧配置的连接条数设置；0 表示不限制。",
            "i18n": _schema_i18n(
                label_en="Max slots",
                label_ja="最大スロット数",
                hint_en="Match the number of connections configured on the SnowLuma side. 0 means unlimited.",
                hint_ja="SnowLuma 側で設定した接続数に合わせてください。0 は無制限。",
            ),
            "label": "最大槽位数量",
            "order": 11,
            "step": 1,
        },
    )
    slot_routing: str = Field(
        default="sticky",
        description=(
            "动作选路策略：sticky 按群号/QQ 号把同一会话固定到同一槽位并保证顺序；"
            "round_robin 在空闲槽位之间轮询，吞吐略高但同一会话可能跨连接。"
        ),
        json_schema_extra={
            "hint": "需要严格保序时用 sticky；只追求分流吞吐时可用 round_robin。",
            "i18n": _schema_i18n(
                label_en="Slot routing",
                label_ja="スロット振り分け",
                hint_en="sticky keeps one chat on one slot for ordering; round_robin spreads load but may reorder.",
                hint_ja="sticky は同じ会話を同じスロットに固定します。round_robin は負荷分散優先です。",
                placeholder_en="sticky / round_robin",
                placeholder_ja="sticky / round_robin",
            ),
            "label": "槽位选路策略",
            "order": 12,
            "placeholder": "sticky",
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


"""反向 WebSocket 连接池。

适配器允许 SnowLuma 用不同路径接入多条连接，每条连接对应一个 ``slot``：

* ``/onebot/v11/ws``         → 默认 slot ``0``
* ``/onebot/v11/ws/{slot}``  → 指定 slot，例如 ``/onebot/v11/ws/1``

每个 slot 拥有自己的发送锁与 echo 等待表，因此一条连接上正在传输的大消息
不会阻塞其它 slot。事件只由唯一的「事件连接」接收，避免重复投递。
"""

from __future__ import annotations

import asyncio
import time
import zlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

DEFAULT_SLOT = "0"
"""不带 slot 后缀的连接使用这个槽位。"""

EVENT_ROLES = frozenset({"event", "universal"})
"""会收到事件的角色；同一时刻只保留一个。"""

SEND_ROLES = frozenset({"api", "universal"})
"""可以承载动作请求的角色。"""


def normalize_slot(raw_value: Any) -> str:
    """把路径片段规范化成槽位标识。

    Args:
        raw_value: 原始槽位字符串，可为空。

    Returns:
        str: 去空白后的槽位标识；为空时回退到 ``0``。
    """

    text = str(raw_value or "").strip()
    return text or DEFAULT_SLOT


def normalize_role(raw_value: Any) -> str:
    """把 ``X-Client-Role`` 头规范化。

    Args:
        raw_value: 原始角色字符串，例如 ``Universal`` / ``Api`` / ``Event``。

    Returns:
        str: 小写角色名；无法识别时按 ``universal`` 处理以兼容旧客户端。
    """

    text = str(raw_value or "").strip().lower()
    return text if text in EVENT_ROLES or text in SEND_ROLES else "universal"


def _session_key(params: Dict[str, Any]) -> str:
    """从动作参数中提取会话键，用于把同一会话固定到同一槽位。"""

    for name in ("group_id", "user_id", "group_code", "uin"):
        value = params.get(name)
        if value not in (None, ""):
            return f"{name}:{value}"
    return ""


@dataclass
class SlotConnection:
    """一条物理连接的运行时状态。"""

    slot: str
    ws: Any
    self_id: str = ""
    role: str = "universal"
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    pending: Dict[str, asyncio.Future[Dict[str, Any]]] = field(default_factory=dict)
    in_flight: int = 0
    connected_at: float = field(default_factory=time.monotonic)
    last_used_at: float = field(default_factory=time.monotonic)

    @property
    def open(self) -> bool:
        """连接是否仍然可用。"""

        return self.ws is not None and not self.ws.closed

    @property
    def can_send(self) -> bool:
        """是否可以承载动作请求。"""

        return self.open and self.role in SEND_ROLES

    @property
    def carries_events(self) -> bool:
        """是否可以接收上行事件。"""

        return self.open and self.role in EVENT_ROLES

    def touch(self) -> None:
        """记录一次使用时间。"""

        self.last_used_at = time.monotonic()

    def idle_seconds(self) -> float:
        """距离上次使用过了多少秒。"""

        return max(0.0, time.monotonic() - self.last_used_at)


class ConnectionPool:
    """按 slot 管理连接，并负责为动作挑选一条连接。"""

    def __init__(self) -> None:
        self._slots: Dict[str, SlotConnection] = {}
        self._round_robin = 0

    def add(self, connection: SlotConnection) -> Optional[SlotConnection]:
        """登记一条连接。

        Args:
            connection: 待登记连接。

        Returns:
            Optional[SlotConnection]: 同 slot 被顶替的旧连接，供调用方关闭。
        """

        previous = self._slots.get(connection.slot)
        self._slots[connection.slot] = connection
        return previous

    def remove(self, connection: SlotConnection) -> bool:
        """移除一条连接。

        Args:
            connection: 待移除连接。

        Returns:
            bool: 该连接确实从池中被移除时返回 ``True``。
        """

        if self._slots.get(connection.slot) is connection:
            self._slots.pop(connection.slot, None)
            return True
        return False

    def get(self, slot: str) -> Optional[SlotConnection]:
        """按槽位取连接。"""

        return self._slots.get(slot)

    def connections(self) -> List[SlotConnection]:
        """返回全部连接，按槽位排序。"""

        return [self._slots[key] for key in sorted(self._slots)]

    def event_connection(self, exclude: Optional[SlotConnection] = None) -> Optional[SlotConnection]:
        """返回当前的事件连接。"""

        for connection in self._slots.values():
            if connection is exclude:
                continue
            if connection.carries_events:
                return connection
        return None

    def has_connection(self) -> bool:
        """是否存在任意可用连接。"""

        return any(connection.open for connection in self._slots.values())

    def pick(
        self,
        params: Optional[Dict[str, Any]] = None,
        *,
        routing: str = "sticky",
        preferred_slot: str = "",
        ordered: bool = True,
        excluded: Sequence[SlotConnection] = (),
    ) -> Optional[SlotConnection]:
        """为一次动作挑选连接。

        规则：

        1. ``preferred_slot`` 命中且可用时直接使用；
        2. ``sticky``：按会话键做稳定哈希，同一会话永远落在同一槽位，保证先后顺序；
        3. ``round_robin``：在负载最低的候选之间轮询；
        4. 没有会话键时选当前在途请求最少的一条。

        Args:
            params: 动作参数，用于提取 ``group_id`` / ``user_id`` 等会话键。
            routing: 选路策略，``sticky`` 或 ``round_robin``。
            preferred_slot: 指定槽位，命中时优先使用。
            ordered: 是否需要保持会话内先后顺序；查询类动作可以设为 ``False``。

        Returns:
            Optional[SlotConnection]: 选中的连接；没有可用连接时返回 ``None``。
        """

        excluded_ids = {id(item) for item in excluded}
        candidates = [item for item in self._slots.values() if item.can_send and id(item) not in excluded_ids]
        if not candidates:
            return None

        preferred = self._slots.get(preferred_slot) if preferred_slot else None
        if preferred is not None and preferred.can_send:
            return preferred

        candidates.sort(key=lambda item: item.slot)
        if not ordered:
            return min(candidates, key=lambda item: (item.in_flight, item.slot))
        key = _session_key(params or {})
        if routing == "round_robin":
            lowest = min(item.in_flight for item in candidates)
            pool = [item for item in candidates if item.in_flight == lowest]
            self._round_robin = (self._round_robin + 1) % len(pool)
            return pool[self._round_robin]
        if key:
            index = zlib.crc32(key.encode("utf-8")) % len(candidates)
            return candidates[index]
        return min(candidates, key=lambda item: (item.in_flight, item.slot))

    def idle_connections(
        self,
        timeout_sec: float,
        *,
        protected_slots: Sequence[str] = (),
    ) -> List[SlotConnection]:
        """列出超过空闲阈值、可以回收的连接。

        Args:
            timeout_sec: 空闲阈值，小于等于 0 表示不回收。
            protected_slots: 不允许回收的槽位（一般是事件连接所在的槽位）。

        Returns:
            List[SlotConnection]: 可回收连接列表。
        """

        if timeout_sec <= 0:
            return []
        protected = set(protected_slots)
        return [
            item
            for item in self._slots.values()
            if item.slot not in protected and item.idle_seconds() >= timeout_sec
        ]

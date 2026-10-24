"""传输实现的公共接口。"""

from __future__ import annotations

from typing import Any, Protocol


class Transport(Protocol):
    """反向 OneBot 传输实现的接口。"""

    @classmethod
    def is_available(cls) -> bool: ...

    def configure(self, server_config: Any, profile_state: Any = None) -> None: ...

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def call_action(self, action_name: str, params: dict[str, Any]) -> dict[str, Any]: ...

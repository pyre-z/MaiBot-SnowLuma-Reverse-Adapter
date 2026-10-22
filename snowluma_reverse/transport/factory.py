"""按传输模式选择 OneBot 传输实现。"""

from typing import Any, Callable, Coroutine

from .forward_client import QQTransportClient
from .reverse_server import QQTransportServer


def create_transport(
    mode: str,
    *,
    logger: Any,
    on_connection_opened: Callable[[], Coroutine[Any, Any, None]],
    on_connection_closed: Callable[[], Coroutine[Any, Any, None]],
    on_payload: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
) -> QQTransportClient | QQTransportServer:
    """创建指定模式的传输实例。"""
    transport_type = QQTransportServer if mode == "server" else QQTransportClient
    return transport_type(logger, on_connection_opened, on_connection_closed, on_payload)

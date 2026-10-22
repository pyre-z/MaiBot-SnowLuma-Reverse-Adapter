"""入站消息编解码（SnowLuma / NapCat 通用，画像钩子见各转换分支）。"""

from __future__ import annotations

from typing import Any, Callable, Dict

from ...services import QQQueryService
from .envelope import QQInboundEnvelopeMixin
from .media import QQInboundMediaMixin
from .segments import QQInboundSegmentsMixin


class QQInboundCodec(QQInboundEnvelopeMixin, QQInboundSegmentsMixin, QQInboundMediaMixin):
    """入站消息编码器。"""

    def __init__(
        self,
        logger: Any,
        query_service: QQQueryService,
        profile_state: Any,
        load_settings: Callable[[], Any],
    ) -> None:
        """初始化入站消息编码器。

        Args:
            logger: 插件日志对象。
            query_service: QQ 查询服务。
            profile_state: 当前连接的客户端画像容器。
            load_settings: 返回当前生效插件配置的回调。
        """
        self._logger = logger
        self._query_service = query_service
        self._profile_state = profile_state
        self._load_settings = load_settings
        self._group_name_cache: Dict[str, str] = {}

    def clear_cache(self) -> None:
        """清空群名缓存（断连时调用，避免跨连接脏数据）。"""
        self._group_name_cache.clear()


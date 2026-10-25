"""Typed configuration sections, preserving the established UI schema."""

from .chat_abilities import QQChatAbilitiesConfig
from .debug import QQDebugConfig
from .filters import QQFilterConfig
from .mute import QQMuteConfig
from .notice import QQNoticeConfig
from .plugin_options import QQPluginOptions
from .reverse_server import QQReverseServerConfig

__all__ = [
    "QQChatAbilitiesConfig",
    "QQDebugConfig",
    "QQFilterConfig",
    "QQMuteConfig",
    "QQNoticeConfig",
    "QQPluginOptions",
    "QQReverseServerConfig",
]

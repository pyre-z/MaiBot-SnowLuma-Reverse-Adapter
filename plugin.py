"""MaiBot 插件加载入口。"""

from .snowluma_reverse.plugin import create_plugin

__all__ = ["create_plugin"]

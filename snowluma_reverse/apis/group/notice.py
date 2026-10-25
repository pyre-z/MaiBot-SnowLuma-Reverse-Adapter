"""QQ 群 API：群公告、群精华与群签到相关 API。"""

from __future__ import annotations

from typing import Any, Dict

from maibot_sdk import API

from ..support import QQApiParamsInput, QQApiSupportMixin


class QQGroupNoticeMixin(QQApiSupportMixin):
    """群公告、群精华与群签到相关 API。"""

    @API(
        "adapter.napcat.group.delete_essence_msg",
        description="移出精华消息",
        version="1",
        public=True,
    )
    async def api_action_delete_essence_msg(
        self, params: QQApiParamsInput = None
    ) -> Dict[str, Any]:
        """调用对端的 ``delete_essence_msg`` 动作。

        Args:
            params: 传递给 对端的动作参数字典；具体字段请参考对端官方文档。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("delete_essence_msg", params)

    @API(
        "adapter.napcat.group.delete_group_notice",
        description="删除群公告",
        version="1",
        public=True,
    )
    async def api_action_delete_group_notice(
        self, params: QQApiParamsInput = None
    ) -> Dict[str, Any]:
        """调用对端的 ``_del_group_notice`` 动作。

        Args:
            params: 传递给 对端的动作参数字典；具体字段请参考对端官方文档。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("_del_group_notice", params)

    @API(
        "adapter.napcat.group.get_essence_msg_list",
        description="获取群精华消息",
        version="1",
        public=True,
    )
    async def api_action_get_essence_msg_list(
        self, params: QQApiParamsInput = None
    ) -> Dict[str, Any]:
        """调用对端的 ``get_essence_msg_list`` 动作。

        Args:
            params: 传递给 对端的动作参数字典；具体字段请参考对端官方文档。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("get_essence_msg_list", params)

    @API(
        "adapter.napcat.group.get_group_notice", description="获取群公告", version="1", public=True
    )
    async def api_action_get_group_notice(self, params: QQApiParamsInput = None) -> Dict[str, Any]:
        """调用对端的 ``_get_group_notice`` 动作。

        Args:
            params: 传递给 对端的动作参数字典；具体字段请参考对端官方文档。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("_get_group_notice", params)

    @API(
        "adapter.napcat.group.send_group_notice", description="发送群公告", version="1", public=True
    )
    async def api_action_send_group_notice(self, params: QQApiParamsInput = None) -> Dict[str, Any]:
        """调用对端的 ``_send_group_notice`` 动作。

        Args:
            params: 传递给 对端的动作参数字典；具体字段请参考对端官方文档。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("_send_group_notice", params)

    @API("adapter.napcat.group.send_group_sign", description="群打卡", version="1", public=True)
    async def api_action_send_group_sign(self, params: QQApiParamsInput = None) -> Dict[str, Any]:
        """调用对端的 ``send_group_sign`` 动作。

        Args:
            params: 传递给 对端的动作参数字典；具体字段请参考对端官方文档。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("send_group_sign", params)

    @API(
        "adapter.napcat.group.set_essence_msg", description="设置精华消息", version="1", public=True
    )
    async def api_action_set_essence_msg(self, params: QQApiParamsInput = None) -> Dict[str, Any]:
        """调用对端的 ``set_essence_msg`` 动作。

        Args:
            params: 传递给 对端的动作参数字典；具体字段请参考对端官方文档。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("set_essence_msg", params)

    @API("adapter.napcat.group.set_group_sign", description="群打卡", version="1", public=True)
    async def api_action_set_group_sign(self, params: QQApiParamsInput = None) -> Dict[str, Any]:
        """调用对端的 ``set_group_sign`` 动作。

        Args:
            params: 传递给 对端的动作参数字典；具体字段请参考对端官方文档。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("set_group_sign", params)

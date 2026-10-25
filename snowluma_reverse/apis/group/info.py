"""QQ 群 API：群信息、群列表、频道与群标签查询相关 API。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from maibot_sdk import API

from ..support import QQApiIdInput, QQApiParamsInput, QQApiSupportMixin


class QQGroupInfoMixin(QQApiSupportMixin):
    """群信息、群列表、频道与群标签查询相关 API。"""

    @API("adapter.napcat.group.get_group_info", description="获取群信息", version="1", public=True)
    async def api_get_group_info(self, group_id: QQApiIdInput) -> Optional[Dict[str, Any]]:
        """获取群信息。

        Args:
            group_id: 群号。

        Returns:
            Optional[Dict[str, Any]]: 群信息字典；失败时返回 ``None``。
        """
        return await self._require_query_service().get_group_info(
            str(self._normalize_positive_int(group_id, "group_id"))
        )

    @API(
        "adapter.napcat.group.get_group_detail_info",
        description="获取群详细信息",
        version="1",
        public=True,
    )
    async def api_get_group_detail_info(self, group_id: QQApiIdInput) -> Optional[Dict[str, Any]]:
        """获取群详细信息。

        Args:
            group_id: 群号。

        Returns:
            Optional[Dict[str, Any]]: 群详细信息字典；失败时返回 ``None``。
        """
        return await self._require_query_service().get_group_detail_info(
            str(self._normalize_positive_int(group_id, "group_id"))
        )

    @API("adapter.napcat.group.get_group_list", description="获取群列表", version="1", public=True)
    async def api_get_group_list(self, no_cache: bool = False) -> Optional[List[Dict[str, Any]]]:
        """获取群列表。

        Args:
            no_cache: 是否禁用缓存。

        Returns:
            Optional[List[Dict[str, Any]]]: 群信息列表；失败时返回 ``None``。
        """
        return await self._require_query_service().get_group_list(no_cache=bool(no_cache))

    @API(
        "adapter.napcat.group.get_group_at_all_remain",
        description="获取群 @ 全体剩余次数",
        version="1",
        public=True,
    )
    async def api_get_group_at_all_remain(self, group_id: QQApiIdInput) -> Optional[Dict[str, Any]]:
        """获取群 @ 全体剩余次数。

        Args:
            group_id: 群号。

        Returns:
            Optional[Dict[str, Any]]: 剩余次数信息；失败时返回 ``None``。
        """
        return await self._require_query_service().get_group_at_all_remain(
            str(self._normalize_positive_int(group_id, "group_id"))
        )

    @API(
        "adapter.napcat.group.get_group_honor_info",
        description="获取群荣誉信息",
        version="1",
        public=True,
    )
    async def api_action_get_group_honor_info(
        self, params: QQApiParamsInput = None
    ) -> Dict[str, Any]:
        """调用对端的 ``get_group_honor_info`` 动作。

        Args:
            params: 传递给 对端的动作参数字典；具体字段请参考对端官方文档。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("get_group_honor_info", params)

    @API(
        "adapter.napcat.group.get_group_info_ex",
        description="获取群详细信息 (扩展)",
        version="1",
        public=True,
    )
    async def api_action_get_group_info_ex(self, params: QQApiParamsInput = None) -> Dict[str, Any]:
        """调用对端的 ``get_group_info_ex`` 动作。

        Args:
            params: 传递给 对端的动作参数字典；具体字段请参考对端官方文档。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("get_group_info_ex", params)

    @API(
        "adapter.napcat.group.get_guild_list", description="获取频道列表", version="1", public=True
    )
    async def api_action_get_guild_list(self, params: QQApiParamsInput = None) -> Dict[str, Any]:
        """调用对端的 ``get_guild_list`` 动作。

        Args:
            params: 传递给 对端的动作参数字典；具体字段请参考对端官方文档。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("get_guild_list", params)

    @API(
        "adapter.napcat.group.get_guild_service_profile",
        description="获取频道个人信息",
        version="1",
        public=True,
    )
    async def api_action_get_guild_service_profile(
        self, params: QQApiParamsInput = None
    ) -> Dict[str, Any]:
        """调用对端的 ``get_guild_service_profile`` 动作。

        Args:
            params: 传递给 对端的动作参数字典；具体字段请参考对端官方文档。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("get_guild_service_profile", params)

    @API(
        "adapter.napcat.group.set_group_search",
        description="设置群搜索选项",
        version="1",
        public=True,
    )
    async def api_action_set_group_search(self, params: QQApiParamsInput = None) -> Dict[str, Any]:
        """调用对端的 ``set_group_search`` 动作。

        Args:
            params: 传递给 对端的动作参数字典；具体字段请参考对端官方文档。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("set_group_search", params)

    @API(
        "adapter.napcat.group.get_group_tags",
        description="获取群标签列表",
        version="1",
        public=True,
    )
    async def api_get_group_tags(self, params: QQApiParamsInput = None) -> Dict[str, Any]:
        """调用对端的 ``get_group_tags`` 动作。

        Args:
            params: 动作参数字典；具体字段由对端动作透传校验。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("get_group_tags", params)

    @API(
        "adapter.napcat.group.get_group_share_link",
        description="获取群分享链接",
        version="1",
        public=True,
    )
    async def api_get_group_share_link(self, params: QQApiParamsInput = None) -> Dict[str, Any]:
        """调用对端的 ``get_group_share_link`` 动作。

        Args:
            params: 动作参数字典；通常必填 ``group_id``，由对端动作透传校验。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("get_group_share_link", params)

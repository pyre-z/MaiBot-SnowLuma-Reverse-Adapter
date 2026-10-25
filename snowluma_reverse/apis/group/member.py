"""QQ 群 API：群成员信息与成员级设置相关 API。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from maibot_sdk import API

from ..support import QQApiIdInput, QQApiParamsInput, QQApiSupportMixin


class QQGroupMemberMixin(QQApiSupportMixin):
    """群成员信息与成员级设置相关 API。"""

    @API(
        "adapter.napcat.group.get_group_member_info",
        description="获取群成员信息",
        version="1",
        public=True,
    )
    async def api_get_group_member_info(
        self,
        group_id: QQApiIdInput,
        user_id: QQApiIdInput,
        no_cache: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """获取群成员信息。

        Args:
            group_id: 群号。
            user_id: 用户号。
            no_cache: 是否禁用缓存。

        Returns:
            Optional[Dict[str, Any]]: 群成员信息字典；失败时返回 ``None``。
        """
        return await self._require_query_service().get_group_member_info(
            group_id=str(self._normalize_positive_int(group_id, "group_id")),
            user_id=str(self._normalize_positive_int(user_id, "user_id")),
            no_cache=bool(no_cache),
        )

    @API(
        "adapter.napcat.group.get_group_member_list",
        description="获取群成员列表",
        version="1",
        public=True,
    )
    async def api_get_group_member_list(
        self,
        group_id: QQApiIdInput,
        no_cache: bool = False,
    ) -> Optional[List[Dict[str, Any]]]:
        """获取群成员列表。

        Args:
            group_id: 群号。
            no_cache: 是否禁用缓存。

        Returns:
            Optional[List[Dict[str, Any]]]: 群成员信息列表；失败时返回 ``None``。
        """
        return await self._require_query_service().get_group_member_list(
            group_id=str(self._normalize_positive_int(group_id, "group_id")),
            no_cache=bool(no_cache),
        )

    @API(
        "adapter.napcat.group.set_group_admin", description="设置群管理员", version="1", public=True
    )
    async def api_action_set_group_admin(self, params: QQApiParamsInput = None) -> Dict[str, Any]:
        """调用对端的 ``set_group_admin`` 动作。

        Args:
            params: 传递给 对端的动作参数字典；具体字段请参考对端官方文档。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("set_group_admin", params)

    @API("adapter.napcat.group.set_group_card", description="设置群名片", version="1", public=True)
    async def api_action_set_group_card(self, params: QQApiParamsInput = None) -> Dict[str, Any]:
        """调用对端的 ``set_group_card`` 动作。

        Args:
            params: 传递给 对端的动作参数字典；具体字段请参考对端官方文档。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("set_group_card", params)

    @API(
        "adapter.napcat.group.set_group_remark", description="设置群备注", version="1", public=True
    )
    async def api_action_set_group_remark(self, params: QQApiParamsInput = None) -> Dict[str, Any]:
        """调用对端的 ``set_group_remark`` 动作。

        Args:
            params: 传递给 对端的动作参数字典；具体字段请参考对端官方文档。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("set_group_remark", params)

    @API(
        "adapter.napcat.group.set_group_special_title",
        description="设置专属头衔",
        version="1",
        public=True,
    )
    async def api_action_set_group_special_title(
        self, params: QQApiParamsInput = None
    ) -> Dict[str, Any]:
        """调用对端的 ``set_group_special_title`` 动作。

        Args:
            params: 传递给 对端的动作参数字典；具体字段请参考对端官方文档。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("set_group_special_title", params)

    @API(
        "adapter.napcat.group.set_group_member_permissions",
        description="设置群成员权限",
        version="1",
        public=True,
    )
    async def api_set_group_member_permissions(
        self, params: QQApiParamsInput = None
    ) -> Dict[str, Any]:
        """调用对端的 ``set_group_member_permissions`` 动作。

        Args:
            params: 动作参数字典；通常必填 ``group_id``、``user_id`` 与权限字段，由对端动作透传校验。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("set_group_member_permissions", params)

    @API(
        "adapter.napcat.group.get_group_admin_settings",
        description="获取群管理设置",
        version="1",
        public=True,
    )
    async def api_get_group_admin_settings(self, params: QQApiParamsInput = None) -> Dict[str, Any]:
        """调用对端的 ``get_group_admin_settings`` 动作。

        Args:
            params: 动作参数字典；通常必填 ``group_id``，由对端动作透传校验。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("get_group_admin_settings", params)

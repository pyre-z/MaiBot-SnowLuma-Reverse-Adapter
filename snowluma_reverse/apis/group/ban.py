"""QQ 群 API：群禁言、踢人与禁言名单相关 API。"""

from __future__ import annotations

from typing import Any, Dict

from maibot_sdk import API

from ..support import QQApiIdInput, QQApiParamsInput, QQApiSupportMixin


class QQGroupBanMixin(QQApiSupportMixin):
    """群禁言、踢人与禁言名单相关 API。"""

    @API(
        "adapter.napcat.group.set_group_ban", description="设置群成员禁言", version="1", public=True
    )
    async def api_set_group_ban(
        self,
        group_id: QQApiIdInput,
        user_id: QQApiIdInput,
        duration: QQApiIdInput,
    ) -> Dict[str, Any]:
        """设置群成员禁言。

        Args:
            group_id: 群号。
            user_id: 用户号。
            duration: 禁言秒数。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        normalized_duration = self._normalize_non_negative_int(duration, "duration")
        if normalized_duration > 2592000:
            raise ValueError("duration 不能超过 2592000 秒")
        return await self._require_query_service().set_group_ban(
            group_id=self._normalize_positive_int(group_id, "group_id"),
            user_id=self._normalize_positive_int(user_id, "user_id"),
            duration=normalized_duration,
        )

    @API(
        "adapter.napcat.group.set_group_whole_ban",
        description="设置群全体禁言",
        version="1",
        public=True,
    )
    async def api_set_group_whole_ban(self, group_id: QQApiIdInput, enable: bool) -> Dict[str, Any]:
        """设置群全体禁言。

        Args:
            group_id: 群号。
            enable: 是否开启全体禁言。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._require_query_service().set_group_whole_ban(
            group_id=self._normalize_positive_int(group_id, "group_id"),
            enable=self._normalize_bool(enable, "enable"),
        )

    @API(
        "adapter.napcat.group.set_group_kick",
        description="踢出单个群成员",
        version="1",
        public=True,
    )
    async def api_set_group_kick(
        self,
        group_id: QQApiIdInput,
        user_id: QQApiIdInput,
        reject_add_request: bool = False,
    ) -> Dict[str, Any]:
        """踢出单个群成员。

        Args:
            group_id: 群号。
            user_id: 用户号。
            reject_add_request: 是否拒绝再次加群。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._require_query_service().set_group_kick(
            group_id=self._normalize_positive_int(group_id, "group_id"),
            user_id=self._normalize_positive_int(user_id, "user_id"),
            reject_add_request=bool(reject_add_request),
        )

    @API(
        "adapter.napcat.group.set_group_kick_members",
        description="批量踢出群成员",
        version="1",
        public=True,
    )
    async def api_set_group_kick_members(
        self,
        group_id: QQApiIdInput,
        user_id: object,
        reject_add_request: bool = False,
    ) -> Dict[str, Any]:
        """批量踢出群成员。

        Args:
            group_id: 群号。
            user_id: 用户号数组。
            reject_add_request: 是否拒绝再次加群。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._require_query_service().set_group_kick_members(
            group_id=self._normalize_positive_int(group_id, "group_id"),
            user_ids=self._normalize_user_id_list(user_id, "user_id"),
            reject_add_request=bool(reject_add_request),
        )

    @API(
        "adapter.napcat.group.get_group_shut_list",
        description="获取群禁言列表",
        version="1",
        public=True,
    )
    async def api_action_get_group_shut_list(
        self, params: QQApiParamsInput = None
    ) -> Dict[str, Any]:
        """调用对端的 ``get_group_shut_list`` 动作。

        Args:
            params: 传递给 对端的动作参数字典；具体字段请参考对端官方文档。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("get_group_shut_list", params)

"""QQ 群 API：群设置、群操作与群扩展动作相关 API。"""

from __future__ import annotations

from typing import Any, Dict

from maibot_sdk import API

from ..support import QQApiIdInput, QQApiParamsInput, QQApiSupportMixin


class QQGroupManageMixin(QQApiSupportMixin):
    """群设置、群操作与群扩展动作相关 API。"""

    @API("adapter.napcat.group.set_group_name", description="设置群名称", version="1", public=True)
    async def api_set_group_name(
        self, group_id: QQApiIdInput, group_name: object
    ) -> Dict[str, Any]:
        """设置群名称。

        Args:
            group_id: 群号。
            group_name: 新群名称。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._require_query_service().set_group_name(
            group_id=self._normalize_positive_int(group_id, "group_id"),
            group_name=self._normalize_non_empty_string(group_name, "group_name"),
        )

    @API(
        "adapter.napcat.group.get_group_ignore_add_request",
        description="获取群被忽略的加群请求",
        version="1",
        public=True,
    )
    async def api_action_get_group_ignore_add_request(
        self, params: QQApiParamsInput = None
    ) -> Dict[str, Any]:
        """调用对端的 ``get_group_ignore_add_request`` 动作。

        Args:
            params: 传递给 对端的动作参数字典；具体字段请参考对端官方文档。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("get_group_ignore_add_request", params)

    @API(
        "adapter.napcat.group.get_group_ignored_notifies",
        description="获取群忽略通知",
        version="1",
        public=True,
    )
    async def api_action_get_group_ignored_notifies(
        self, params: QQApiParamsInput = None
    ) -> Dict[str, Any]:
        """调用对端的 ``get_group_ignored_notifies`` 动作。

        Args:
            params: 传递给 对端的动作参数字典；具体字段请参考对端官方文档。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("get_group_ignored_notifies", params)

    @API(
        "adapter.napcat.group.get_group_system_msg",
        description="获取群系统消息",
        version="1",
        public=True,
    )
    async def api_action_get_group_system_msg(
        self, params: QQApiParamsInput = None
    ) -> Dict[str, Any]:
        """调用对端的 ``get_group_system_msg`` 动作。

        Args:
            params: 传递给 对端的动作参数字典；具体字段请参考对端官方文档。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("get_group_system_msg", params)

    @API("adapter.napcat.group.group_poke", description="发送戳一戳", version="1", public=True)
    async def api_action_group_poke(self, params: QQApiParamsInput = None) -> Dict[str, Any]:
        """调用对端的 ``group_poke`` 动作。

        Args:
            params: 传递给 对端的动作参数字典；具体字段请参考对端官方文档。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("group_poke", params)

    @API(
        "adapter.napcat.group.handle_quick_operation_internal",
        description="处理快速操作",
        version="1",
        public=True,
    )
    async def api_action_handle_quick_operation_internal(
        self, params: QQApiParamsInput = None
    ) -> Dict[str, Any]:
        """调用对端的 ``.handle_quick_operation`` 动作。

        Args:
            params: 传递给 对端的动作参数字典；具体字段请参考对端官方文档。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action(".handle_quick_operation", params)

    @API("adapter.napcat.group.send_group_msg", description="发送群消息", version="1", public=True)
    async def api_action_send_group_msg(self, params: QQApiParamsInput = None) -> Dict[str, Any]:
        """调用对端的 ``send_group_msg`` 动作。

        Args:
            params: 传递给 对端的动作参数字典；具体字段请参考对端官方文档。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("send_group_msg", params)

    @API(
        "adapter.napcat.group.set_group_add_option",
        description="设置群加群选项",
        version="1",
        public=True,
    )
    async def api_action_set_group_add_option(
        self, params: QQApiParamsInput = None
    ) -> Dict[str, Any]:
        """调用对端的 ``set_group_add_option`` 动作。

        Args:
            params: 传递给 对端的动作参数字典；具体字段请参考对端官方文档。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("set_group_add_option", params)

    @API(
        "adapter.napcat.group.set_group_add_request",
        description="处理加群请求",
        version="1",
        public=True,
    )
    async def api_action_set_group_add_request(
        self, params: QQApiParamsInput = None
    ) -> Dict[str, Any]:
        """调用对端的 ``set_group_add_request`` 动作。

        Args:
            params: 传递给 对端的动作参数字典；具体字段请参考对端官方文档。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("set_group_add_request", params)

    @API("adapter.napcat.group.set_group_leave", description="退出群组", version="1", public=True)
    async def api_action_set_group_leave(self, params: QQApiParamsInput = None) -> Dict[str, Any]:
        """调用对端的 ``set_group_leave`` 动作。

        Args:
            params: 传递给 对端的动作参数字典；具体字段请参考对端官方文档。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("set_group_leave", params)

    @API(
        "adapter.napcat.group.set_group_portrait",
        description="设置群头像",
        version="1",
        public=True,
    )
    async def api_action_set_group_portrait(
        self, params: QQApiParamsInput = None
    ) -> Dict[str, Any]:
        """调用对端的 ``set_group_portrait`` 动作。

        Args:
            params: 传递给 对端的动作参数字典；具体字段请参考对端官方文档。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("set_group_portrait", params)

    @API(
        "adapter.napcat.group.set_group_robot_add_option",
        description="设置群机器人加群选项",
        version="1",
        public=True,
    )
    async def api_action_set_group_robot_add_option(
        self, params: QQApiParamsInput = None
    ) -> Dict[str, Any]:
        """调用对端的 ``set_group_robot_add_option`` 动作。

        Args:
            params: 传递给 对端的动作参数字典；具体字段请参考对端官方文档。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("set_group_robot_add_option", params)

    @API(
        "adapter.napcat.group.set_group_reaction",
        description="设置群消息表情回应",
        version="1",
        public=True,
    )
    async def api_set_group_reaction(self, params: QQApiParamsInput = None) -> Dict[str, Any]:
        """调用对端的 ``set_group_reaction`` 动作。

        Args:
            params: 动作参数字典；必填 ``message_id`` 与 ``code``，可选 ``is_set``。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。

        Raises:
            ValueError: 当必填参数缺失或不合法时抛出。
        """
        normalized_params = self._normalize_params(params)
        normalized_params["message_id"] = self._normalize_message_id(
            normalized_params.get("message_id"), "message_id"
        )
        normalized_params["code"] = self._normalize_non_empty_string(
            normalized_params.get("code"), "code"
        )
        return await self._call_napcat_action("set_group_reaction", normalized_params)

    @API(
        "adapter.napcat.group.get_group_todo_list",
        description="获取群待办列表",
        version="1",
        public=True,
    )
    async def api_get_group_todo_list(self, params: QQApiParamsInput = None) -> Dict[str, Any]:
        """调用对端的 ``get_group_todo_list`` 动作。

        Args:
            params: 动作参数字典；通常必填 ``group_id``，由对端动作透传校验。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("get_group_todo_list", params)

    @API("adapter.napcat.group.set_group_todo", description="创建群待办", version="1", public=True)
    async def api_create_group_todo(self, params: QQApiParamsInput = None) -> Dict[str, Any]:
        """调用对端的 ``set_group_todo`` 动作。

        Args:
            params: 动作参数字典；通常必填 ``group_id`` 与待办内容，由对端动作透传校验。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("set_group_todo", params)

    @API(
        "adapter.napcat.group.complete_group_todo",
        description="完成群待办",
        version="1",
        public=True,
    )
    async def api_complete_group_todo(self, params: QQApiParamsInput = None) -> Dict[str, Any]:
        """调用对端的 ``complete_group_todo`` 动作。

        Args:
            params: 动作参数字典；通常必填待办标识，由对端动作透传校验。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("complete_group_todo", params)

    @API(
        "adapter.napcat.group.cancel_group_todo", description="取消群待办", version="1", public=True
    )
    async def api_cancel_group_todo(self, params: QQApiParamsInput = None) -> Dict[str, Any]:
        """调用对端的 ``cancel_group_todo`` 动作。

        Args:
            params: 动作参数字典；通常必填待办标识，由对端动作透传校验。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("cancel_group_todo", params)

    @API("adapter.napcat.group.add_group_tag", description="新增群标签", version="1", public=True)
    async def api_add_group_tag(self, params: QQApiParamsInput = None) -> Dict[str, Any]:
        """调用对端的 ``add_group_tag`` 动作。

        Args:
            params: 动作参数字典；通常必填标签名称，由对端动作透传校验。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("add_group_tag", params)

    @API(
        "adapter.napcat.group.delete_group_tag", description="删除群标签", version="1", public=True
    )
    async def api_delete_group_tag(self, params: QQApiParamsInput = None) -> Dict[str, Any]:
        """调用对端的 ``delete_group_tag`` 动作。

        Args:
            params: 动作参数字典；通常必填标签标识，由对端动作透传校验。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("delete_group_tag", params)

    @API(
        "adapter.napcat.file.test_download_stream",
        description="测试下载流",
        version="1",
        public=True,
    )
    async def api_action_test_download_stream(
        self, params: QQApiParamsInput = None
    ) -> Dict[str, Any]:
        """调用对端的 ``test_download_stream`` 动作。

        Args:
            params: 传递给 对端的动作参数字典；具体字段请参考对端官方文档。

        Returns:
            Dict[str, Any]: 对端返回的原始响应字典。
        """
        return await self._call_napcat_action("test_download_stream", params)

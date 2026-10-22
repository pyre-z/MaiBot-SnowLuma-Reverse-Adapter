"""业务 API 转发行为测试。"""

from __future__ import annotations

import inspect
from typing import Any, Dict, List

import pytest

from snowluma_reverse.apis.account import QQAccountApiMixin
from snowluma_reverse.apis.group import QQGroupApiMixin
from snowluma_reverse.apis.message import QQMessageApiMixin
from snowluma_reverse.apis.qzone import QQQzoneApiMixin


class FakeActionService:
    def __init__(self):
        self.calls: List[tuple[str, Dict[str, Any]]] = []

    async def call_action(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        self.calls.append((action, params))
        return {"status": "ok", "retcode": 0, "data": {}}


class Runtime:
    def __init__(self):
        self.action_service = FakeActionService()
        self.profile = None


def make_service(mixin_cls, profile_supports_qzone=True):
    class Service(mixin_cls):
        def _ensure_runtime_components(self) -> None:
            return None

        def _require_runtime_bundle(self):
            return type("Bundle", (), {"profile": type("Profile", (), {"supports_qzone": profile_supports_qzone, "client_type": "snowluma"})()})()

    service = Service()
    service._action_service = FakeActionService()
    service._query_service = None
    return service


GROUP_CASES = [
    ("api_set_group_reaction", "set_group_reaction"),
    ("api_get_group_todo_list", "get_group_todo_list"),
    ("api_create_group_todo", "set_group_todo"),
    ("api_complete_group_todo", "complete_group_todo"),
    ("api_cancel_group_todo", "cancel_group_todo"),
    ("api_get_group_tags", "get_group_tags"),
    ("api_add_group_tag", "add_group_tag"),
    ("api_delete_group_tag", "delete_group_tag"),
    ("api_get_group_share_link", "get_group_share_link"),
    ("api_set_group_member_permissions", "set_group_member_permissions"),
    ("api_get_group_admin_settings", "get_group_admin_settings"),
]
MESSAGE_CASES = [
    ("api_get_msg_emoji_likes", "get_msg_emoji_likes"),
    ("api_send_custom_face", "send_custom_face"),
    ("api_fetch_sys_faces", "fetch_sys_faces"),
    ("api_search_sys_faces", "search_sys_faces"),
    ("api_upload_forward_msg", "upload_forward_msg"),
]


def assert_forward(service, method_name, action, params):
    result = getattr(service, method_name)(params)
    coro = result
    import asyncio
    response = asyncio.run(coro)
    assert response == {"status": "ok", "retcode": 0, "data": {}}
    assert service._action_service.calls[-1] == (action, params)
    return response


def test_group_apis_forward_exact_actions_and_params():
    service = make_service(QQGroupApiMixin)
    params = {"group_id": 123, "user_id": 456, "is_set": True}
    params["message_id"] = 12345
    params["code"] = "88"
    for method, action in GROUP_CASES:
        assert_forward(service, method, action, params)


def test_message_apis_forward_exact_actions_and_params():
    service = make_service(QQMessageApiMixin)
    params = {"message_id": 123, "emoji_id": "88", "group_id": 123, "forward": True}
    for method, action in MESSAGE_CASES:
        assert_forward(service, method, action, params)


def test_qzone_and_account_apis_forward_exact_actions_and_params():
    qzone = make_service(QQQzoneApiMixin)
    params = {"msg_id": "detail-1", "cmt_id": 2}
    assert_forward(qzone, "api_get_qzone_msg_detail", "get_qzone_msg_detail", params)

    account = make_service(QQAccountApiMixin)
    params = {"uin": 10001, "categoryId": 3, "categoryName": "家人"}
    assert_forward(account, "api_set_friends_category", "set_friends_category", params)


def test_required_param_validation():
    group = make_service(QQGroupApiMixin)
    with pytest.raises(ValueError, match="message_id"):
        import asyncio
        asyncio.run(group.api_set_group_reaction({"code": "1"}))

    message = make_service(QQMessageApiMixin)
    with pytest.raises(ValueError, match="group_id"):
        import asyncio
        asyncio.run(message.api_send_custom_face({"emoji_id": "88"}))

    account = make_service(QQAccountApiMixin)
    with pytest.raises(ValueError, match="categoryId"):
        import asyncio
        asyncio.run(account.api_set_friends_category({"uin": 10001}))


def test_api_decorator_names_use_napcat_prefix():
    """装饰器元数据必须在类函数上可读；若 SDK 版本剥离元数据则跳过。"""
    mixins = (QQAccountApiMixin, QQGroupApiMixin, QQMessageApiMixin, QQQzoneApiMixin)
    found = 0
    for mixin in mixins:
        for _name, member in inspect.getmembers(mixin, inspect.isfunction):
            info = inspect.getattr_static(member, "__maibot_component_info__", None)
            if info is None:
                info = inspect.getattr_static(member, "_component_info", None)
            if info is not None and info.name.startswith("adapter."):
                found += 1
                if info.name.startswith(("adapter.account.", "adapter.group.", "adapter.message.", "adapter.qzone.")):
                    assert info.name.startswith("adapter.napcat.")
    if not found:
        pytest.skip("当前 SDK 未把组件元数据暴露在函数属性上")

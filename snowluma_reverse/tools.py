"""LLM 工具组件。"""

from __future__ import annotations

import aiohttp
import time
from typing import Any, Dict, List, Mapping, Optional

from maibot_sdk import Tool
from maibot_sdk.types import ToolParameterInfo, ToolParamType

from .data.faces import QQ_FACE_DESCRIPTIONS
from .dress import DressError, fetch_dress, format_summary, pick
from .profile import MSG_ACTION_STYLE_GENERIC
from .render import parse_color, render_card, to_base64_source


def _matches_scoped_identifier(allowed_values: List[str], current_value: str) -> bool:
    """兼容 ``platform:id`` 与纯 ID 两种配置格式。"""
    normalized_current_value = str(current_value or "").strip()
    if not normalized_current_value:
        return False
    for allowed_value in allowed_values:
        normalized_allowed_value = str(allowed_value or "").strip()
        if normalized_allowed_value == normalized_current_value or normalized_allowed_value.endswith(f":{normalized_current_value}"):
            return True
    return False


class QQLlmToolsMixin:
    @Tool(
        "open_private_chat",
        platforms="qq",
        description=(
            "向指定 QQ 用户发送一条私聊消息，用于主动开启私聊。"
        ),
        parameters=[
            ToolParameterInfo(
                name="user_id",
                param_type=ToolParamType.STRING,
                description="要开启私聊的 QQ 用户 ID，必须是正整数。",
                required=True,
            ),
            ToolParameterInfo(
                name="message",
                param_type=ToolParamType.STRING,
                description="要发送给该用户的第一条私聊消息。",
                required=True,
            ),
        ],
        enabled=False,
        visibility="visible",
    )
    async def tool_open_private_chat(
        self,
        user_id: Any = "",
        message: str = "",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """主动向指定用户发送私聊消息。"""
        del kwargs

        try:
            normalized_user_id = str(self._normalize_positive_int(user_id, "user_id"))
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

        normalized_message = str(message or "").strip()
        if not normalized_message:
            return {"success": False, "error": "私聊消息不能为空"}

        runtime_bundle = self._require_runtime_bundle()
        settings = self._load_settings()
        login_info = await runtime_bundle.query_service.get_login_info()
        account_id = str((login_info or {}).get("user_id") or "").strip()
        if not account_id:
            return {"success": False, "error": "无法获取当前登录账号"}

        open_session_result = await self.ctx.chat.open_session(
            platform="qq",
            chat_type="private",
            user_id=normalized_user_id,
            account_id=account_id,
            scope=settings.server.connection_id,
        )
        if not isinstance(open_session_result, Mapping) or not bool(open_session_result.get("success", False)):
            error = str(open_session_result.get("error") or "").strip() if isinstance(open_session_result, Mapping) else ""
            return {
                "success": False,
                "error": error or "打开私聊会话失败",
                "open_session_result": open_session_result,
            }

        # 发送动作按画像取值：NapCat 用 send_private_msg，SnowLuma 用通用 send_msg。
        profile = runtime_bundle.profile
        if profile.msg_action_style == MSG_ACTION_STYLE_GENERIC:
            action_name = "send_msg"
            action_params: Dict[str, Any] = {
                "message_type": "private",
                "user_id": int(normalized_user_id),
                "message": [{"type": "text", "data": {"text": normalized_message}}],
            }
        else:
            action_name = "send_private_msg"
            action_params = {
                "user_id": int(normalized_user_id),
                "message": [{"type": "text", "data": {"text": normalized_message}}],
            }

        try:
            response = await runtime_bundle.action_service.call_action(action_name, action_params)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        response_data = response.get("data", {})
        message_id = str(response_data.get("message_id") or "") if isinstance(response_data, Mapping) else ""
        self.ctx.logger.info(
            f"已主动开启私聊: user_id={normalized_user_id} message_id={message_id or '<unknown>'}"
        )
        return {
            "success": True,
            "content": (
                f"已向用户 {normalized_user_id} 发送私聊消息。"
                "请确认宿主适配器策略允许该私聊的入站消息。"
            ),
            "user_id": normalized_user_id,
            "stream_id": str(open_session_result.get("session_id") or open_session_result.get("stream_id") or ""),
            "session": open_session_result.get("stream") or {},
            "message_id": message_id,
        }

    @Tool(
        "get_qq_by_msg_id",
        platforms="qq",
        description="根据当前聊天中的消息 ID 获取该消息发送者的 QQ 用户 ID。",
        parameters=[
            ToolParameterInfo(
                name="msg_id",
                param_type=ToolParamType.STRING,
                description="目标用户发送的消息 ID。",
                required=True,
            ),
        ],
        enabled=False,
        visibility="visible",
    )
    async def tool_get_qq_by_msg_id(
        self,
        msg_id: str = "",
        stream_id: str = "",
        chat_id: str = "",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """根据消息 ID 查询该消息发送者的 QQ 号。"""
        del kwargs

        normalized_msg_id = str(msg_id or "").strip()
        if not normalized_msg_id:
            return {"success": False, "error": "缺少目标消息 ID"}

        target_stream_id = str(stream_id or chat_id or "").strip()
        query_result = await self.ctx.message.get_by_id(
            normalized_msg_id,
            stream_id=target_stream_id,
            include_binary_data=False,
        )
        if not isinstance(query_result, Mapping):
            return {"success": False, "error": f"未找到消息: {normalized_msg_id}", "msg_id": normalized_msg_id}

        message_info = query_result.get("message_info", {})
        user_info = message_info.get("user_info", {}) if isinstance(message_info, Mapping) else {}
        user_info = user_info if isinstance(user_info, Mapping) else {}
        user_id = str(user_info.get("user_id") or "").strip()
        if not user_id:
            return {"success": False, "error": f"消息 {normalized_msg_id} 缺少发送者 QQ 号", "msg_id": normalized_msg_id}

        user_nickname = str(user_info.get("user_nickname") or "").strip()
        user_cardname = str(user_info.get("user_cardname") or "").strip()
        display_name = user_cardname or user_nickname or user_id
        group_info = message_info.get("group_info", {})
        group_info = group_info if isinstance(group_info, Mapping) else {}
        return {
            "success": True,
            "content": f"消息 {normalized_msg_id} 的发送者是 {display_name}，QQ 号为 {user_id}。",
            "msg_id": normalized_msg_id,
            "user_id": user_id,
            "qq": user_id,
            "user_nickname": user_nickname,
            "user_cardname": user_cardname,
            "display_name": display_name,
            "platform": str(query_result.get("platform") or "").strip(),
            "session_id": str(query_result.get("session_id") or target_stream_id).strip(),
            "group_id": str(group_info.get("group_id") or "").strip(),
            "group_name": str(group_info.get("group_name") or "").strip(),
        }

    @Tool(
        "send_poke",
        platforms="qq",
        description=(
            "对指定消息的发送者发送戳一戳。"
        ),
        parameters=[
            ToolParameterInfo(
                name="msg_id",
                param_type=ToolParamType.STRING,
                description="目标用户发送的消息 ID，戳一戳对象是该消息的发送者。",
                required=True,
            ),
        ],
        enabled=False,
        visibility="visible",
    )
    async def tool_send_poke(
        self,
        msg_id: Any = "",
        stream_id: str = "",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """对指定消息的发送者发送戳一戳。"""
        del kwargs

        normalized_msg_id = str(msg_id or "").strip()
        if not normalized_msg_id:
            return {"success": False, "error": "缺少目标消息 ID"}

        # 通过消息 ID 定位发送者与消息所在群。
        query_result = await self.ctx.message.get_by_id(
            normalized_msg_id,
            stream_id=stream_id,
            include_binary_data=False,
        )
        message_info = query_result.get("message_info", {}) if isinstance(query_result, Mapping) else {}
        user_info = message_info.get("user_info", {}) if isinstance(message_info, Mapping) else {}
        target_user_id = str(user_info.get("user_id") or "").strip()
        if not target_user_id:
            return {"success": False, "error": f"未找到消息 {normalized_msg_id} 或其缺少发送者信息"}
        try:
            normalized_user_id = self._normalize_positive_int(target_user_id, "user_id")
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

        # 群上下文由消息自身决定：群聊消息带群号，私聊消息无群号则发送好友戳一戳。
        message_group_info = message_info.get("group_info") if isinstance(message_info, Mapping) else None
        message_group_info = message_group_info if isinstance(message_group_info, Mapping) else {}
        normalized_group_id: Optional[int] = None
        resolved_group_id = str(message_group_info.get("group_id") or "").strip()
        if resolved_group_id:
            try:
                normalized_group_id = self._normalize_positive_int(resolved_group_id, "group_id")
            except ValueError as exc:
                return {"success": False, "error": str(exc)}

        try:
            await self._require_query_service().send_poke(
                user_id=normalized_user_id,
                group_id=normalized_group_id,
            )
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        target_display_name = (
            str(user_info.get("user_cardname") or "").strip()
            or str(user_info.get("user_nickname") or "").strip()
            or str(normalized_user_id)
        )
        scope_text = f"群 {normalized_group_id} 中" if normalized_group_id is not None else "私聊中"
        self.ctx.logger.info(
            f"已发送戳一戳: user_id={normalized_user_id} group_id={normalized_group_id or '<private>'} "
            f"msg_id={normalized_msg_id}"
        )
        return {
            "success": True,
            "content": f"已在{scope_text}向 {target_display_name} 发送戳一戳。",
            "user_id": str(normalized_user_id),
            "group_id": str(normalized_group_id) if normalized_group_id is not None else "",
            "msg_id": normalized_msg_id,
        }

    @Tool(
        "recall_message",
        platforms="qq",
        description=(
            "撤回一条 QQ 消息。撤回自己发送的消息通常限 2 分钟内；"
            "撤回他人消息需要机器人是群管理员。message_id 使用聊天记录中的消息 ID。"
        ),
        parameters=[
            ToolParameterInfo(
                name="message_id",
                param_type=ToolParamType.STRING,
                description="要撤回的消息 ID，来自聊天记录中的消息 ID。",
                required=True,
            ),
        ],
        enabled=False,
        visibility="visible",
    )
    async def tool_recall_message(
        self,
        message_id: Any = "",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """撤回指定消息。"""
        del kwargs

        # 聊天记录中的消息 ID 即平台真实 ID：入站消息直接透传对端 message_id，
        # 机器人自发消息会经 message_id_echo 回填为平台 ID。
        try:
            normalized_message_id = self._normalize_message_id(message_id, "message_id")
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

        try:
            await self._require_query_service().delete_message(message_id=normalized_message_id)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        self.ctx.logger.info(f"已撤回消息: message_id={normalized_message_id}")
        return {
            "success": True,
            "content": f"已撤回消息 {normalized_message_id}。",
            "message_id": str(normalized_message_id),
        }

    @Tool(
        "mute",
        platforms="qq",
        description=(
            "在群聊中根据消息 ID 禁言该消息的发送者。"
            "适用于刷屏、违规发言、用户主动要求被禁言等情况。"
            "群主、管理员和保护名单中的用户不会被禁言；时长会被限制在配置范围内。"
        ),
        parameters=[
            ToolParameterInfo(
                name="msg_id",
                param_type=ToolParamType.STRING,
                description="要禁言的目标所发送的消息 ID。",
                required=True,
            ),
            ToolParameterInfo(
                name="duration",
                param_type=ToolParamType.INTEGER,
                description="禁言时长，单位秒，正整数。",
                required=True,
            ),
            ToolParameterInfo(
                name="reason",
                param_type=ToolParamType.STRING,
                description="禁言原因，可选。",
                required=False,
            ),
        ],
        enabled=False,
        visibility="visible",
    )
    async def tool_mute(
        self,
        msg_id: Any = "",
        duration: Any = "",
        group_id: Any = "",
        stream_id: str = "",
        reason: str = "",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """根据消息 ID 禁言发送者。"""
        del kwargs

        normalized_group_id = str(group_id or "").strip()
        if not normalized_group_id:
            return {"success": False, "error": "禁言仅支持群聊，当前会话缺少群号"}

        settings = self._load_settings()
        mute_settings = settings.mute

        # 群白名单：非空时仅放行名单内的群。
        allowed_groups = [str(item).strip() for item in mute_settings.allowed_groups if str(item).strip()]
        if allowed_groups and not _matches_scoped_identifier(allowed_groups, normalized_group_id):
            return {"success": False, "error": f"群 {normalized_group_id} 不在禁言白名单内"}

        normalized_msg_id = str(msg_id or "").strip()
        if not normalized_msg_id:
            return {"success": False, "error": "缺少目标消息 ID"}

        try:
            normalized_duration = self._normalize_positive_int(duration, "duration")
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
        if normalized_duration < mute_settings.min_duration:
            normalized_duration = mute_settings.min_duration
        if normalized_duration > mute_settings.max_duration:
            normalized_duration = mute_settings.max_duration

        # 通过消息 ID 定位发送者，复用宿主消息查询能力。
        query_result = await self.ctx.message.get_by_id(
            normalized_msg_id,
            stream_id=stream_id,
            include_binary_data=False,
        )
        message_info = query_result.get("message_info", {}) if isinstance(query_result, Mapping) else {}
        user_info = message_info.get("user_info", {}) if isinstance(message_info, Mapping) else {}
        target_user_id = str(user_info.get("user_id") or "").strip()
        if not target_user_id:
            return {"success": False, "error": f"未找到消息 {normalized_msg_id} 或其缺少发送者信息"}
        target_display_name = (
            str(user_info.get("user_cardname") or "").strip()
            or str(user_info.get("user_nickname") or "").strip()
            or target_user_id
        )

        # 保护名单：配置内用户一律不禁言。
        admin_users = [str(item).strip() for item in mute_settings.admin_users if str(item).strip()]
        if _matches_scoped_identifier(admin_users, target_user_id):
            return {"success": False, "error": f"用户 {target_display_name} 在禁言保护名单中，无法被禁言"}

        # 平台角色检查：群主和管理员不能被禁言，避免对端报错前的无效调用。
        member_info = await self._require_query_service().get_group_member_info(
            group_id=normalized_group_id,
            user_id=target_user_id,
            no_cache=True,
        )
        target_role = str((member_info or {}).get("role") or "").strip().lower()
        if target_role in {"owner", "admin"}:
            role_text = "群主" if target_role == "owner" else "管理员"
            return {"success": False, "error": f"{target_display_name} 是{role_text}，不能被禁言"}

        normalized_reason = str(reason or "").strip()
        try:
            await self._require_query_service().set_group_ban(
                group_id=self._normalize_positive_int(normalized_group_id, "group_id"),
                user_id=self._normalize_positive_int(target_user_id, "user_id"),
                duration=normalized_duration,
            )
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        self.ctx.logger.info(
            f"已禁言: group_id={normalized_group_id} user_id={target_user_id} "
            f"target={target_display_name} duration={normalized_duration} reason={normalized_reason or '<none>'}"
        )
        return {
            "success": True,
            "content": f"已禁言 {target_display_name}，时长 {normalized_duration} 秒。",
            "group_id": normalized_group_id,
            "user_id": target_user_id,
            "duration": normalized_duration,
            "reason": normalized_reason,
        }

    @Tool(
        "react_emoji",
        platforms="qq",
        description=(
            "给一条消息贴表情表态（消息回应），如点赞、爱心等。"
            "常用表情 ID：76=赞、66=爱心、63=玫瑰、21=可爱、5=流泪、78=握手（戏谑的志同道合）、144=喝彩。424=续标识(表达刺激或极度同意）"
        ),
        parameters=[
            ToolParameterInfo(
                name="message_id",
                param_type=ToolParamType.STRING,
                description="要贴表情的消息 ID，来自聊天记录中的消息 ID。",
                required=True,
            ),
            ToolParameterInfo(
                name="emoji_id",
                param_type=ToolParamType.INTEGER,
                description="QQ 表情 ID，如 76 表示赞。",
                required=True,
            ),
        ],
        enabled=False,
        visibility="visible",
    )
    async def tool_react_emoji(
        self,
        message_id: Any = "",
        emoji_id: Any = "",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """给指定消息贴表情表态。"""
        del kwargs

        try:
            normalized_message_id = self._normalize_message_id(message_id, "message_id")
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

        try:
            normalized_emoji_id = self._normalize_positive_int(emoji_id, "emoji_id")
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

        try:
            await self._require_query_service().set_message_emoji_like(
                message_id=normalized_message_id,
                emoji_id=normalized_emoji_id,
                set_like=True,
            )
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        emoji_name = QQ_FACE_DESCRIPTIONS.get(str(normalized_emoji_id), "")
        emoji_text = f"[{emoji_name}]" if emoji_name else f"[表情{normalized_emoji_id}]"
        self.ctx.logger.info(
            f"已贴表情表态: message_id={normalized_message_id} emoji_id={normalized_emoji_id}"
        )
        return {
            "success": True,
            "content": f"已对消息 {normalized_message_id} 贴上{emoji_text}表情。",
            "message_id": str(normalized_message_id),
            "emoji_id": normalized_emoji_id,
            "emoji_name": emoji_name or None,
        }

    @Tool(
        "list_chat_streams",
        platforms="qq",
        description=(
            "列出当前所有活跃的 QQ 聊天流（群聊和私聊），"
            "返回每个流的显示名称、类型、群号或用户 QQ 号。"
            "常用于在转发消息前选择目标聊天流。"
        ),
        parameters=[],
        visibility="visible",
        enabled=False,
    )
    async def tool_list_chat_streams(self, **kwargs: Any) -> Dict[str, Any]:
        """列出所有活跃聊天流。"""
        del kwargs

        streams = await self.ctx.chat.get_all_streams(platform="qq")
        if not isinstance(streams, list):
            error = str((streams or {}).get("error") or "") if isinstance(streams, Mapping) else ""
            return {"success": False, "error": error or "获取聊天流列表失败"}

        # 显示名优先用实际名称（群名 / xxx的私聊），而不是裸 session_id。
        stream_entries: List[Dict[str, Any]] = []
        for stream in streams:
            if not isinstance(stream, Mapping):
                continue
            group_id = str(stream.get("group_id") or "").strip()
            user_id = str(stream.get("user_id") or "").strip()
            is_group = bool(stream.get("is_group_session"))
            if is_group:
                display_name = str(stream.get("group_name") or "").strip() or f"群 {group_id}"
            else:
                peer_name = (
                    str(stream.get("user_cardname") or "").strip()
                    or str(stream.get("user_nickname") or "").strip()
                )
                display_name = f"{peer_name}的私聊" if peer_name else (f"QQ {user_id} 的私聊" if user_id else "未知私聊")
            if not group_id and not user_id:
                continue
            stream_entries.append(
                {
                    "display_name": display_name,
                    "chat_type": "group" if is_group else "private",
                    "group_id": group_id,
                    "user_id": user_id,
                    "stream_id": str(stream.get("stream_id") or stream.get("session_id") or "").strip(),
                }
            )

        if not stream_entries:
            return {"success": True, "content": "当前没有活跃的聊天流。", "streams": [], "count": 0}

        lines: List[str] = []
        for index, entry in enumerate(stream_entries, start=1):
            if entry["chat_type"] == "group":
                lines.append(f"{index}. [群聊] {entry['display_name']}（群号 {entry['group_id']}）")
            else:
                lines.append(f"{index}. [私聊] {entry['display_name']}（QQ {entry['user_id']}）")
        return {
            "success": True,
            "content": f"当前活跃聊天流共 {len(stream_entries)} 个：\n" + "\n".join(lines),
            "streams": stream_entries,
            "count": len(stream_entries),
        }

    @Tool(
        "forward_messages",
        platforms="qq",
        description=(
            "把一批消息打包成合并转发消息，发送到指定的群或私聊。"
            "目标群号或用户 QQ 号可先用 list_chat_streams 查询。"
            "消息 ID 来自聊天记录，将按传入顺序组成转发记录。"
            "也可用 attach_pic 选择上下文或工具返回的图片，图片追加到消息记录之后，发送者为机器人自己。"
        ),
        parameters=[
            ToolParameterInfo(
                name="message_ids",
                param_type=ToolParamType.ARRAY,
                description="要转发的消息 ID 列表，按顺序排列。",
                required=False,
                items_schema={"type": "string", "description": "聊天记录中的消息 ID"},
            ),
            ToolParameterInfo(
                name="attach_pic",
                param_type=ToolParamType.ARRAY,
                description="要打包的上下文图片，按顺序追加为机器人发送的节点；与 message_ids 至少提供一项。",
                required=False,
                items_schema={
                    "type": "object",
                    "properties": {
                        "msg_id": {"type": "string", "description": "图片所在的 IM 消息 ID；与 media_index 二选一。"},
                        "media_index": {
                            "type": "string",
                            "description": "上下文媒体索引，如 tool_result:call_x:1；与 msg_id 二选一。",
                        },
                        "index": {"type": "integer", "minimum": 0, "default": 0, "description": "图片序号，从 0 开始。"},
                    },
                },
            ),
            ToolParameterInfo(
                name="target_group_id",
                param_type=ToolParamType.STRING,
                description="目标群号；与 target_user_id 二选一。",
                required=False,
            ),
            ToolParameterInfo(
                name="target_user_id",
                param_type=ToolParamType.STRING,
                description="目标私聊用户 QQ 号；与 target_group_id 二选一。",
                required=False,
            ),
        ],
        enabled=False,
        visibility="visible",
    )
    async def tool_forward_messages(
        self,
        message_ids: Any = None,
        target_group_id: Any = "",
        target_user_id: Any = "",
        stream_id: str = "",
        attach_pic: Any = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """把一批消息打包成合并转发发送到目标聊天。"""
        del kwargs

        if message_ids is None:
            message_ids = []
        if attach_pic is None:
            attach_pic = []
        if not isinstance(message_ids, list) or not isinstance(attach_pic, list):
            return {"success": False, "error": "message_ids 和 attach_pic 必须是数组"}

        # 保序去重，避免同一消息被重复查询与重复出现在转发记录中。
        normalized_message_ids = list(dict.fromkeys(str(item or "").strip() for item in message_ids))
        normalized_message_ids = [item for item in normalized_message_ids if item]
        if not normalized_message_ids and not attach_pic:
            return {"success": False, "error": "message_ids 或 attach_pic 至少提供一项"}
        if len(normalized_message_ids) + len(attach_pic) > 50:
            return {"success": False, "error": "单次转发最多支持 50 个消息或图片节点"}
        if attach_pic and not stream_id:
            return {"success": False, "error": "选择上下文图片需要当前聊天流 stream_id"}

        selected_images: List[Dict[str, Any]] = []
        for attachment in attach_pic:
            if not isinstance(attachment, dict):
                return {"success": False, "error": "attach_pic 每项必须是图片引用对象"}
            msg_id = str(attachment.get("msg_id") or "").strip()
            media_index = str(attachment.get("media_index") or "").strip()
            index = attachment.get("index", 0)
            if bool(msg_id) == bool(media_index):
                return {"success": False, "error": "图片引用的 msg_id 与 media_index 必须二选一"}
            if isinstance(index, bool) or not isinstance(index, int) or index < 0:
                return {"success": False, "error": "图片 index 必须是非负整数"}
            selected_images.append({"source_id": msg_id or media_index, "index": index})

        normalized_target_group_id = str(target_group_id or "").strip()
        normalized_target_user_id = str(target_user_id or "").strip()
        if bool(normalized_target_group_id) == bool(normalized_target_user_id):
            return {"success": False, "error": "target_group_id 与 target_user_id 必须二选一"}

        # 逐条取回消息并构造转发节点；查询范围限定在当前聊天流。
        forward_nodes: List[Dict[str, Any]] = []
        for message_id in normalized_message_ids:
            query_result = await self.ctx.message.get_by_id(
                message_id,
                stream_id=stream_id,
                include_binary_data=True,
            )
            message_dict = query_result if isinstance(query_result, Mapping) else None
            message_info = message_dict.get("message_info", {}) if isinstance(message_dict, Mapping) else {}
            user_info = message_info.get("user_info", {}) if isinstance(message_info, Mapping) else {}
            raw_message = message_dict.get("raw_message") if isinstance(message_dict, Mapping) else None
            sender_user_id = str(user_info.get("user_id") or "").strip()
            if not isinstance(raw_message, list) or not sender_user_id:
                return {"success": False, "error": f"未找到消息 {message_id} 或其缺少发送者信息"}
            forward_nodes.append(
                {
                    "user_id": sender_user_id,
                    "user_nickname": str(user_info.get("user_nickname") or "").strip(),
                    "user_cardname": str(user_info.get("user_cardname") or "").strip(),
                    "content": raw_message,
                }
            )

        runtime_bundle = self._require_runtime_bundle()
        # 上下文图片由 Host 在当前聊天流中解析，转发节点使用实际登录的机器人身份。
        if selected_images:
            bot_id = runtime_bundle.runtime_state.account_id
            login_info = await runtime_bundle.query_service.get_login_info()
            if not bot_id or not isinstance(login_info, dict) or str(login_info.get("user_id")) != bot_id:
                return {"success": False, "error": "无法确认当前连接的机器人身份"}
            bot_name = str(login_info.get("nickname") or "").strip()
            if not bot_name:
                return {"success": False, "error": "当前登录机器人缺少昵称"}
            for selection in selected_images:
                image_message = await self.ctx.message.get_by_id(
                    selection["source_id"],
                    stream_id=stream_id,
                    include_binary_data=True,
                    context_image_index=selection["index"],
                )
                image_segments = image_message.get("raw_message") if isinstance(image_message, Mapping) else None
                if (
                    not isinstance(image_segments, list)
                    or len(image_segments) != 1
                    or image_segments[0].get("type") != "image"
                    or not image_segments[0].get("binary_data_base64")
                ):
                    return {"success": False, "error": f"无法读取上下文图片: {selection['source_id']} index={selection['index']}"}
                forward_nodes.append({"user_id": bot_id, "user_nickname": bot_name, "content": image_segments})

        # 组装 forward 段并复用出站编解码链路：参数键按画像取值，消息段统一编码。
        outbound_message: Dict[str, Any] = {
            "message_info": {"group_info": {}, "user_info": {}, "additional_config": {}},
            "raw_message": [{"type": "forward", "data": forward_nodes}],
        }
        route: Dict[str, Any] = {"group_id": normalized_target_group_id, "user_id": normalized_target_user_id}
        try:
            actions = runtime_bundle.outbound_codec.build_outbound_actions(outbound_message, route)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        try:
            for action_name, params in actions:
                await runtime_bundle.action_service.call_action(action_name, params)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        target_text = (
            f"群 {normalized_target_group_id}" if normalized_target_group_id else f"用户 {normalized_target_user_id} 的私聊"
        )
        self.ctx.logger.info(
            f"已发送合并转发: target={target_text} count={len(forward_nodes)} "
            f"message_ids={normalized_message_ids}"
        )
        return {
            "success": True,
            "content": f"已把 {len(forward_nodes)} 条消息打包成合并转发发送到{target_text}。",
            "target": target_text,
            "forwarded_count": len(forward_nodes),
            "message_ids": normalized_message_ids,
        }

    # ─────────────── 个性装扮 / 聊天气泡 ───────────────

    _DRESS_CACHE: Dict[str, Any] = {}
    _DRESS_TTL_SEC = 3600.0
    _DRESS_COOKIE_TTL_SEC = 900.0

    async def _resolve_stream_route(self, stream_id: str) -> Optional[Dict[str, str]]:
        """按 stream_id 反查当前会话的群号 / 对方 QQ。"""
        target = str(stream_id or "").strip()
        if not target:
            return None
        streams = await self.ctx.chat.get_all_streams(platform="qq")
        if not isinstance(streams, list):
            return None
        for stream in streams:
            if not isinstance(stream, Mapping):
                continue
            candidate = str(stream.get("stream_id") or stream.get("session_id") or "").strip()
            if candidate != target:
                continue
            return {
                "chat_type": "group" if bool(stream.get("is_group_session")) else "private",
                "group_id": str(stream.get("group_id") or "").strip(),
                "user_id": str(stream.get("user_id") or "").strip(),
            }
        return None

    async def _send_image_url(self, route: Mapping[str, str], url: str) -> tuple[bool, str]:
        """把图片直链作为图片段发到指定会话。"""
        bundle = self._require_runtime_bundle()
        segments = [{"type": "image", "data": {"file": url}}]
        generic = bundle.profile.msg_action_style == MSG_ACTION_STYLE_GENERIC

        if route.get("chat_type") == "group":
            group_id = str(route.get("group_id") or "").strip()
            if not group_id:
                return False, "会话缺少群号"
            action = "send_msg" if generic else "send_group_msg"
            params: Dict[str, Any] = {"group_id": int(group_id), "message": segments}
            if generic:
                params["message_type"] = "group"
        else:
            user_id = str(route.get("user_id") or "").strip()
            if not user_id:
                return False, "会话缺少用户 QQ 号"
            action = "send_msg" if generic else "send_private_msg"
            params = {"user_id": int(user_id), "message": segments}
            if generic:
                params["message_type"] = "private"

        try:
            response = await bundle.action_service.call_action(action, params)
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)
        if not isinstance(response, Mapping) or response.get("retcode") not in (0, None):
            return False, f"发送失败: {response}"
        return True, ""

    _DRESS_SLICE_CACHE: Dict[str, Dict[str, bytes]] = {}

    async def _fetch_bytes(self, url: str, timeout: float = 10.0) -> bytes:
        """下载一个二进制资源（头像 / 九宫格切片）。"""
        client_timeout = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP {response.status}: {url}")
                return await response.read()

    async def _load_dress(self, uin: int) -> Dict[str, Any]:
        """带缓存地取某人的装扮（装扮 1h / cookie 15min）。"""
        cache_key = f"dress:{uin}"
        cached = self._DRESS_CACHE.get(cache_key)
        if isinstance(cached, tuple) and time.time() - cached[0] < self._DRESS_TTL_SEC:
            return cached[1]

        cookie_key = "cookies:vip.qq.com"
        cached_cookie = self._DRESS_CACHE.get(cookie_key)
        if isinstance(cached_cookie, tuple) and time.time() - cached_cookie[0] < self._DRESS_COOKIE_TTL_SEC:
            cookies = cached_cookie[1]
        else:
            bundle = self._require_runtime_bundle()
            try:
                response = await bundle.action_service.call_action(
                    "get_credentials", {"domain": "vip.qq.com"}
                )
            except Exception as exc:  # noqa: BLE001
                raise DressError("auth", f"获取登录态失败: {exc}") from exc
            if not isinstance(response, Mapping) or response.get("retcode") != 0:
                raise DressError("auth", f"获取登录态失败: {response}")
            cookies = str((response.get("data") or {}).get("cookies") or "")
            self._DRESS_CACHE[cookie_key] = (time.time(), cookies)

        data = await fetch_dress(cookies, uin)
        self._DRESS_CACHE[cache_key] = (time.time(), data)
        return data

    async def _load_bubble_slices(self, bubble: Mapping[str, Any]) -> Dict[str, bytes]:
        """按 itemId 缓存气泡九宫格切片。"""
        item_id = str(bubble.get("item_id") or "")
        if not item_id:
            return {}
        cached = self._DRESS_SLICE_CACHE.get(item_id)
        if cached:
            return cached

        slices: Dict[str, bytes] = {}
        material = bubble.get("material") or {}
        if isinstance(material, Mapping):
            for label, url in material.items():
                if not isinstance(url, str) or not url.startswith("http"):
                    continue
                try:
                    slices[str(label)] = await self._fetch_bytes(url)
                except Exception:  # noqa: BLE001
                    continue
        self._DRESS_SLICE_CACHE[item_id] = slices
        return slices

    @Tool(
        "get_qq_dress",
        platforms="qq",
        description=(
            "查询某个 QQ 用户正在使用的个性装扮：聊天气泡、字体、主题、名片、挂件等。"
            "user_id 留空表示查机器人自己。"
            "返回装扮名称、itemId 与素材直链；气泡会额外给出九宫格切图地址。"
            "send_image=true 时把气泡预览图发到当前聊天。"
        ),
        parameters=[
            ToolParameterInfo(
                name="user_id",
                param_type=ToolParamType.STRING,
                description="要查询的 QQ 号；留空表示当前机器人账号。",
                required=False,
            ),
            ToolParameterInfo(
                name="send_image",
                param_type=ToolParamType.BOOLEAN,
                description="是否把查到的气泡预览图发到当前聊天，默认否。",
                required=False,
            ),
        ],
        enabled=False,
        visibility="visible",
    )
    async def tool_get_qq_dress(
        self,
        user_id: Any = "",
        send_image: Any = False,
        stream_id: str = "",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """查询目标用户的个性装扮，可选附带气泡预览图。"""
        del kwargs

        bundle = self._require_runtime_bundle()
        raw_user_id = str(user_id or "").strip()
        nickname = ""

        if raw_user_id:
            try:
                target_uin = self._normalize_positive_int(raw_user_id, "user_id")
            except ValueError as exc:
                return {"success": False, "error": str(exc)}
        else:
            login_info = await bundle.query_service.get_login_info()
            login_info = login_info if isinstance(login_info, Mapping) else {}
            try:
                target_uin = self._normalize_positive_int(login_info.get("user_id"), "user_id")
            except ValueError:
                return {"success": False, "error": "无法获取当前登录账号"}
            nickname = str(login_info.get("nickname") or "")

        try:
            data = await self._load_dress(target_uin)
        except DressError as exc:
            return {"success": False, "error": str(exc), "kind": exc.kind}

        content = format_summary(data, nickname)
        bubble = pick(data.get("items") or [], 2) or {}
        preview_url = str(bubble.get("preview_url") or "")

        image_sent = False
        image_error = ""
        want_image = str(send_image).strip().lower() in {"1", "true", "yes", "on"}
        if want_image and preview_url and stream_id:
            route = await self._resolve_stream_route(stream_id)
            if route is None:
                image_error = "未找到当前会话，预览图未发送"
            else:
                image_sent, image_error = await self._send_image_url(route, preview_url)

        result: Dict[str, Any] = {
            "success": True,
            "content": content,
            "target_uin": str(data.get("target_uin") or ""),
            "is_svip": bool(data.get("is_svip")),
            "items": data.get("items") or [],
            "bubble": bubble,
            "preview_url": preview_url,
            "image_sent": image_sent,
        }
        if image_error:
            result["image_error"] = image_error
        return result

    @Tool(
        "render_message_card",
        platforms="qq",
        description=(
            "把当前聊天里的一条消息渲染成聊天卡片图片并发到本会话："
            "发送者头像 + 该用户的聊天气泡 + 消息文字。"
            "适合「把这句话画成 QQ 消息」「看看我的气泡配这句话长什么样」。"
            "注意：头像框与个性字体取不到可用素材，头像框不画、字体用系统中文黑体。"
        ),
        parameters=[
            ToolParameterInfo(
                name="msg_id",
                param_type=ToolParamType.STRING,
                description="要渲染的消息 ID。",
                required=True,
            ),
            ToolParameterInfo(
                name="with_avatar",
                param_type=ToolParamType.BOOLEAN,
                description="是否绘制发送者头像，默认是。",
                required=False,
            ),
            ToolParameterInfo(
                name="max_chars",
                param_type=ToolParamType.INTEGER,
                description="每行最多几个中文字符（半角字符算半个），默认 15。",
                required=False,
            ),
            ToolParameterInfo(
                name="mirror",
                param_type=ToolParamType.BOOLEAN,
                description="头像在左时镜像气泡（尾巴朝左，跟 QQ 收到的消息一致），默认是。",
                required=False,
            ),
        ],
        enabled=False,
        visibility="visible",
    )
    async def tool_render_message_card(
        self,
        msg_id: str = "",
        with_avatar: Any = True,
        max_chars: Any = 15,
        mirror: Any = True,
        stream_id: str = "",
        chat_id: str = "",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """把一条消息渲染成聊天卡片并发送。"""
        del kwargs

        normalized_msg_id = str(msg_id or "").strip()
        if not normalized_msg_id:
            return {"success": False, "error": "缺少目标消息 ID"}

        target_stream_id = str(stream_id or chat_id or "").strip()
        query = await self.ctx.message.get_by_id(
            normalized_msg_id,
            stream_id=target_stream_id,
            include_binary_data=False,
        )
        if not isinstance(query, Mapping):
            return {"success": False, "error": f"未找到消息: {normalized_msg_id}"}

        payload: Mapping[str, Any] = query
        if isinstance(query.get("message"), Mapping):
            payload = query["message"]

        message_info = payload.get("message_info")
        message_info = message_info if isinstance(message_info, Mapping) else {}
        user_info = message_info.get("user_info")
        user_info = user_info if isinstance(user_info, Mapping) else {}

        raw_uin = str(user_info.get("user_id") or "").strip()
        try:
            sender_uin = self._normalize_positive_int(raw_uin, "user_id")
        except ValueError:
            return {"success": False, "error": "该消息没有有效的发送者 QQ 号"}

        text = str(payload.get("processed_plain_text") or "").strip()
        if not text:
            chunks: List[str] = []
            raw_message = payload.get("raw_message")
            if isinstance(raw_message, list):
                for segment in raw_message:
                    if not isinstance(segment, Mapping):
                        continue
                    data = segment.get("data")
                    data = data if isinstance(data, Mapping) else segment
                    piece = data.get("text")
                    if isinstance(piece, str) and piece:
                        chunks.append(piece)
            text = "".join(chunks).strip()
        if not text:
            return {"success": False, "error": "这条消息没有可渲染的文字内容"}

        route = await self._resolve_stream_route(target_stream_id)
        if route is None:
            return {"success": False, "error": "未找到当前会话，无法发送渲染图"}

        try:
            dress = await self._load_dress(sender_uin)
        except DressError:
            dress = {"items": []}

        bubble = pick(dress.get("items") or [], 2) or {}
        slices = await self._load_bubble_slices(bubble) if bubble else {}

        avatar_bytes = b""
        want_avatar = str(with_avatar).strip().lower() not in {"false", "0", "no", "off"}
        if want_avatar:
            try:
                avatar_bytes = await self._fetch_bytes(
                    f"https://q.qlogo.cn/g?b=qq&nk={sender_uin}&s=640", timeout=8.0
                )
            except Exception:  # noqa: BLE001
                avatar_bytes = b""

        want_mirror = str(mirror).strip().lower() not in {"false", "0", "no", "off"}

        try:
            chars_per_line = max(4, min(int(max_chars), 40))
        except (TypeError, ValueError):
            chars_per_line = 15

        try:
            png = render_card(
                text=text,
                slices=slices,
                avatar_bytes=avatar_bytes,
                text_color=parse_color(bubble.get("text_color")),
                max_chars_per_line=chars_per_line,
                mirror=want_mirror,
            )
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "error": f"渲染失败: {exc}"}

        ok, error = await self._send_image_url(route, to_base64_source(png))
        if not ok:
            return {"success": False, "error": f"图片发送失败: {error}"}

        return {
            "success": True,
            "content": "已把这条消息渲染成 QQ 消息卡片并发到当前会话。",
            "msg_id": normalized_msg_id,
            "sender_uin": str(sender_uin),
            "bubble_item_id": bubble.get("item_id") or 0,
            "used_bubble": bool(slices),
            "image_bytes": len(png),
        }



"""LLM 工具组件。"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from maibot_sdk import Tool
from maibot_sdk.types import ToolParameterInfo, ToolParamType

from .data.faces import QQ_FACE_DESCRIPTIONS
from .profile import MSG_ACTION_STYLE_GENERIC


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
            scope=settings.transport_config().connection_id,
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


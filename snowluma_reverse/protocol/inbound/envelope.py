"""Inbound event/message envelope normalization."""

from __future__ import annotations

import time
from typing import Any, Dict, Mapping

from ...types import QQPayload

class QQInboundEnvelopeMixin:
    async def build_message_dict(
        self,
        payload: QQPayload,
        self_id: str,
        sender_user_id: str,
        sender: Mapping[str, Any],
    ) -> Dict[str, Any]:
        """构造 Host 侧可接受的 ``MessageDict``。

        Args:
            payload: 原始消息事件。
            self_id: 当前机器人账号 ID。
            sender_user_id: 发送者用户 ID。
            sender: 发送者信息字典。

        Returns:
            Dict[str, Any]: 规范化后的 ``MessageDict``。
        """
        message_type = str(payload.get("message_type") or "").strip() or "private"
        group_id = str(payload.get("group_id") or "").strip()
        # 群临时私聊也携带来源 group_id；会话类型必须以 message_type 为准。
        is_group_chat = message_type == "group"
        # SnowLuma 的推送不带 group_name，需要查询对端补全（移植自 SnowLuma 适配器）；
        # NapCat 推送自带该字段，查询不会触发。
        group_name = await self._resolve_group_name(payload, group_id) if is_group_chat else ""
        user_nickname = str(sender.get("nickname") or sender.get("card") or sender_user_id).strip() or sender_user_id
        user_cardname = str(sender.get("card") or "").strip() or None

        raw_message, is_at, platform_card_payloads = await self.convert_segments_with_metadata(payload, self_id)
        if not raw_message:
            raw_message = [self._build_text_segment("[unsupported]")]

        plain_text = self.build_plain_text(raw_message)
        timestamp_seconds = payload.get("time")
        if not isinstance(timestamp_seconds, (int, float)):
            timestamp_seconds = time.time()

        additional_config: Dict[str, Any] = {
            "napcat_message_type": message_type,
            "client_type": self._profile_state.profile.client_type,
        }
        if is_group_chat and group_id:
            additional_config["platform_io_target_group_id"] = group_id
        else:
            additional_config["platform_io_target_user_id"] = sender_user_id
            if group_id:
                additional_config["platform_io_temp_group_id"] = group_id
        if platform_card_payloads:
            additional_config["platform_card_payloads"] = platform_card_payloads

        message_info: Dict[str, Any] = {
            "user_info": {
                "user_id": sender_user_id,
                "user_nickname": user_nickname,
                "user_cardname": user_cardname,
            },
            "additional_config": additional_config,
        }
        if is_group_chat and group_id:
            message_info["group_info"] = {"group_id": group_id, "group_name": group_name}

        # message_id 是平台侧消息的主键，缺失时无法引用/去重/撤回；
        # 明确报错丢弃该消息，不合成内部 ID 掩盖对端数据问题。
        message_id = str(payload.get("message_id") or "").strip()
        if not message_id:
            raise ValueError("入站消息缺少 message_id")
        has_picture = any(
            isinstance(segment, Mapping) and str(segment.get("type") or "") in {"image", "picture"}
            for segment in raw_message
        )
        return {
            "message_id": message_id,
            "timestamp": str(float(timestamp_seconds)),
            "platform": "qq",
            "account_id": self_id,
            "scope": None,
            "message_info": message_info,
            "raw_message": raw_message,
            "is_mentioned": is_at,
            "is_at": is_at,
            "is_emoji": False,
            "is_picture": has_picture,
            "is_command": plain_text.startswith("/"),
            "is_notify": False,
            "session_id": "",
            "processed_plain_text": plain_text,
            "display_message": plain_text,
        }

    async def _resolve_group_name(self, payload: Mapping[str, Any], group_id: str) -> str:
        """解析群名称：优先推送字段，缺失时查询对端 ``get_group_info`` 并缓存。

        移植自 SnowLuma 适配器：SnowLuma 的推送不带 ``group_name``，
        仅靠 payload 会全部退化成 ``group_<id>``。

        Args:
            payload: 原始消息事件。
            group_id: 当前消息所在群号；私聊消息为空字符串。

        Returns:
            str: 解析出的群名称；私聊或查询失败时返回空串或 ``group_<id>`` 占位。
        """
        if not group_id:
            return ""

        raw_group_name = str(payload.get("group_name") or "").strip()
        if raw_group_name:
            self._group_name_cache[group_id] = raw_group_name
            return raw_group_name

        cached_group_name = self._group_name_cache.get(group_id, "")
        if cached_group_name:
            return cached_group_name

        try:
            group_info = await self._query_service.get_group_info(group_id)
        except Exception as exc:
            self._logger.debug(f"查询群名称失败: group_id={group_id} error={exc}")
            return f"group_{group_id}"

        if group_info is not None:
            resolved_group_name = str(group_info.get("group_name") or "").strip()
            if resolved_group_name:
                self._group_name_cache[group_id] = resolved_group_name
                return resolved_group_name

        return f"group_{group_id}"

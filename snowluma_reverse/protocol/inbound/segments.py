"""Inbound message segment normalization and dispatch."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Tuple

from ...data.faces import QQ_FACE_DESCRIPTIONS, QQ_FACE_EMOJIS
from ...types import QQPayload, QQSegment, QQSegments
from ...types import QQIncomingSegment, QQIncomingSegments
from ..notice.helpers import normalize_optional_string
from .cards import QQInboundCardMixin
from .text import QQInboundTextMixin
from uuid import uuid4


class QQInboundSegmentsMixin(QQInboundCardMixin, QQInboundTextMixin):
    async def convert_segments(self, payload: QQPayload, self_id: str) -> Tuple[QQSegments, bool]:
        """将 OneBot 消息段转换为 Host 消息段结构。

        Args:
            payload: OneBot 原始消息事件。
            self_id: 当前机器人账号 ID。

        Returns:
            Tuple[QQSegments, bool]: 转换后的消息段列表，以及是否 @ 到当前机器人。

        Raises:
            ValueError: 当载荷缺少结构化 ``message`` 段列表时抛出。
        """
        raw_message, is_at, _platform_card_payloads = await self.convert_segments_with_metadata(payload, self_id)
        return raw_message, is_at

    async def convert_segments_with_metadata(
        self,
        payload: QQPayload,
        self_id: str,
    ) -> Tuple[QQSegments, bool, List[Dict[str, Any]]]:
        """将 OneBot 消息段转换为 Host 消息段结构，并收集平台卡片元数据。

        Args:
            payload: OneBot 原始消息事件。
            self_id: 当前机器人账号 ID。

        Returns:
            Tuple[QQSegments, bool, List[Dict[str, Any]]]: 转换后的消息段列表、是否 @ 到当前机器人，
            以及不参与纯文本处理的平台卡片元数据。
        """
        message_payload = self._require_message_segments(payload)
        group_id = str(payload.get("group_id") or "").strip()
        platform_card_payloads: List[Dict[str, Any]] = []
        raw_message, is_at = await self._convert_incoming_segments(
            message_payload,
            self_id,
            group_id,
            platform_card_payloads=platform_card_payloads,
        )
        return raw_message, is_at, platform_card_payloads

    def _require_message_segments(self, payload: QQPayload) -> QQIncomingSegments:
        """从载荷中提取结构化消息段列表。

        SnowLuma 部分事件会以纯字符串形式携带 ``message`` 字段，
        此时整体视为单个文本段。

        Args:
            payload: 对端原始载荷。

        Returns:
            QQIncomingSegments: 规范化后的结构化消息段列表。

        Raises:
            ValueError: 当 ``message`` 字段为空或不可识别时抛出。
        """
        message_payload = payload.get("message")
        if isinstance(message_payload, str):
            message_text = message_payload.strip()
            if not message_text:
                raise ValueError("入站消息 message 字段为空")
            return [
                QQIncomingSegment(
                    type="text",
                    data={"text": message_payload},
                )
            ]
        if not isinstance(message_payload, list):
            raise ValueError("入站消息缺少结构化 message 段列表")

        normalized_segments = self._normalize_incoming_segments(message_payload)
        if not normalized_segments:
            raise ValueError("入站消息未包含可识别的结构化消息段")
        return normalized_segments

    def _normalize_incoming_segments(self, message_payload: List[Any]) -> QQIncomingSegments:
        """规范化 NapCat / OneBot 原始消息段列表。

        Args:
            message_payload: 原始 ``message`` 字段值。

        Returns:
            QQIncomingSegments: 过滤并标准化后的消息段列表。
        """
        normalized_segments: QQIncomingSegments = []
        for segment in message_payload:
            if not isinstance(segment, Mapping):
                continue
            segment_type = str(segment.get("type") or "").strip()
            segment_data = segment.get("data", {})
            if not segment_type or not isinstance(segment_data, Mapping):
                continue
            normalized_segments.append(
                QQIncomingSegment(
                    type=segment_type,
                    data=dict(segment_data),
                )
            )
        return normalized_segments

    async def _convert_incoming_segments(
        self,
        message_payload: QQIncomingSegments,
        self_id: str,
        group_id: str,
        *,
        platform_card_payloads: Optional[List[Dict[str, Any]]] = None,
        resolve_reply_details: bool = True,
    ) -> Tuple[QQSegments, bool]:
        """将结构化 OneBot 消息段转换为 Host 消息段结构。

        Args:
            message_payload: NapCat / OneBot 结构化消息段列表。
            self_id: 当前机器人账号 ID。
            group_id: 当前消息所在群号；私聊消息为空字符串。
            resolve_reply_details: 是否查询引用目标详情；转发节点和引用预览只保留目标 ID。

        Returns:
            Tuple[QQSegments, bool]: 转换后的消息段列表，以及是否 @ 到当前机器人。
        """
        converted_segments: QQSegments = []
        at_target_cache: Dict[str, Tuple[Optional[str], Optional[str]]] = {}
        is_at = False
        for segment_index, segment in enumerate(message_payload):
            segment_type = str(segment.get("type") or "").strip()
            segment_data = segment.get("data", {})
            if not isinstance(segment_data, Mapping):
                segment_data = {}

            if segment_type == "text":
                if text_value := str(segment_data.get("text") or ""):
                    # SnowLuma 会在 Markdown 后附加相同正文的 text 兼容段，只消费一次正文。
                    if segment_index > 0:
                        previous_segment = message_payload[segment_index - 1]
                        if (
                            previous_segment["type"] == "markdown"
                            and previous_segment["data"].get("content") == text_value
                        ):
                            continue
                    converted_segments.append(self._build_text_segment(text_value))
                continue

            if segment_type == "markdown":
                markdown_content = segment_data.get("content")
                if not isinstance(markdown_content, str):
                    raise ValueError("Markdown 消息段的 content 必须是字符串")
                if markdown_content:
                    converted_segments.append(self._build_text_segment(markdown_content))
                continue

            if segment_type == "at":
                if target_user_id := str(segment_data.get("qq") or "").strip():
                    if target_user_id in at_target_cache:
                        target_user_nickname, target_user_cardname = at_target_cache[target_user_id]
                    else:
                        target_user_nickname, target_user_cardname = await self._resolve_at_target_info(
                            group_id=group_id,
                            target_user_id=target_user_id,
                        )
                        at_target_cache[target_user_id] = (target_user_nickname, target_user_cardname)

                    converted_segments.append(
                        {
                            "type": "at",
                            "data": {
                                "target_user_id": target_user_id,
                                "target_user_nickname": target_user_nickname,
                                "target_user_cardname": target_user_cardname,
                            },
                        }
                    )
                    if self_id and target_user_id == self_id:
                        is_at = True
                continue

            if segment_type == "reply":
                if reply_segment := await self._build_reply_segment(
                    segment_data, resolve_details=resolve_reply_details
                ):
                    converted_segments.append(reply_segment)
                continue

            if segment_type == "face":
                converted_segments.append(self._build_face_text_segment(segment_data))
                continue

            if segment_type == "image":
                converted_segments.append(await self._build_image_like_segment(segment_data, is_emoji=False))
                continue

            if segment_type == "record":
                converted_segments.append(await self._build_record_segment(segment_data))
                continue

            if segment_type == "video":
                converted_segments.append(self._build_video_text_segment(segment_data))
                continue

            if segment_type == "file":
                converted_segments.append(self._build_file_text_segment(segment_data))
                continue

            if segment_type == "flash_file":
                name = str(segment_data.get("name") or segment_data.get("title") or segment_data.get("file") or "未知文件")
                size = str(segment_data.get("size") or segment_data.get("file_size") or segment_data.get("file_set_id") or "未知大小")
                url = str(segment_data.get("url") or segment_data.get("thumb") or segment_data.get("file_url") or "")
                converted_segments.append(self._build_text_segment(f"[闪传文件: {name}，{size}{'，' + url if url else ''}]"))
                continue

            if segment_type == "mface":
                summary = str(segment_data.get("summary") or "").strip()
                type_id = str(segment_data.get("type_id") or segment_data.get("emoji_id") or segment_data.get("id") or "未知")
                converted_segments.append(self._build_text_segment(summary or f"[表情:{type_id}]"))
                continue

            if segment_type == "poke":
                converted_segments.append(self._build_text_segment("[戳一戳]"))
                continue

            if segment_type == "inline_keyboard":
                logger = getattr(self, "_logger", None)
                if logger is not None:
                    logger.debug("SnowLuma inline_keyboard 原始 JSON 已忽略")
                converted_segments.append(self._build_text_segment("[内联键盘]"))
                continue

            if segment_type == "json":
                converted_segments.extend(
                    await self._build_json_segments(
                        segment_data,
                        platform_card_payloads=platform_card_payloads,
                    )
                )
                continue

            if segment_type == "forward":
                if forward_segment := await self._build_forward_segment(segment_data):
                    converted_segments.append(forward_segment)
                continue

            if segment_type in {"xml", "share"}:
                converted_segments.append(self._build_text_segment(f"[{segment_type}]"))
                continue

            logger = getattr(self, "_logger", None)
            if logger is not None:
                logger.debug(f"未知消息段已降级为占位文本: {segment_type}")
            converted_segments.append(self._build_text_segment(f"[不支持的消息段: {segment_type or 'unknown'}]"))

        return converted_segments, is_at

    async def _resolve_at_target_info(
        self,
        group_id: str,
        target_user_id: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        """解析 ``at`` 目标的展示信息。

        Args:
            group_id: 当前消息所在群号；私聊消息为空字符串。
            target_user_id: 被 ``at`` 的用户号。

        Returns:
            Tuple[Optional[str], Optional[str]]: 依次返回 QQ 昵称和群昵称。
        """
        if not target_user_id or target_user_id == "all":
            return None, None

        target_user_nickname: Optional[str] = None
        target_user_cardname: Optional[str] = None

        if group_id:
            member_info = await self._query_service.get_group_member_info(group_id, target_user_id, no_cache=True)
            if member_info is not None:
                target_user_nickname = normalize_optional_string(member_info.get("nickname"))
                target_user_cardname = normalize_optional_string(member_info.get("card"))

        if target_user_nickname or target_user_cardname:
            return target_user_nickname, target_user_cardname

        stranger_info = await self._query_service.get_stranger_info(target_user_id)
        if stranger_info is None:
            return None, None

        return normalize_optional_string(stranger_info.get("nickname")), target_user_cardname

    @staticmethod
    def _build_text_segment(text: str) -> QQSegment:
        """构造一条纯文本 Host 消息段。

        Args:
            text: 文本内容。

        Returns:
            QQSegment: Host 侧纯文本消息段。
        """
        return {"type": "text", "data": text}

    @staticmethod
    def _normalize_inbound_reply_id(value: Any) -> str:
        """规范化入站引用消息 ID，过滤 OneBot 的空引用。

        Args:
            value: ``reply`` 段的原始 id 值。

        Returns:
            str: 规范化后的消息 ID；空引用返回空字符串。
        """

        normalized_value = str(value or "").strip()
        if not normalized_value:
            return ""
        try:
            reply_id = int(normalized_value)
        except ValueError:
            return normalized_value
        if reply_id == 0:
            return ""
        return str(reply_id)

    async def _build_reply_segment(
        self, segment_data: Mapping[str, Any], *, resolve_details: bool = True
    ) -> Optional[QQSegment]:
        """构造回复消息段。

        SnowLuma / OneBot 会推送 ``id=0`` 的空引用，统一过滤。

        Args:
            segment_data: OneBot ``reply`` 段的 ``data`` 字典。
            resolve_details: 是否查询引用目标的内容和发送者信息。

        Returns:
            Optional[QQSegment]: 转换后的回复消息段；缺少有效消息 ID 或查询不到原消息时返回 ``None``。
        """
        target_message_id = self._normalize_inbound_reply_id(segment_data.get("id"))
        if not target_message_id:
            return None

        reply_payload: Dict[str, Any] = {"target_message_id": target_message_id}
        message_detail = await self._query_service.get_message_detail(target_message_id) if resolve_details else None
        if resolve_details and message_detail is None:
            return None
        if message_detail is not None:
            sender = message_detail.get("sender", {})
            if not isinstance(sender, Mapping):
                sender = {}
            reply_payload["target_message_content"] = await self._build_reply_preview_text(message_detail)
            reply_payload["target_message_sender_id"] = (
                str(message_detail.get("user_id") or sender.get("user_id") or "").strip() or None
            )
            reply_payload["target_message_sender_nickname"] = str(sender.get("nickname") or "").strip() or None
            reply_payload["target_message_sender_cardname"] = str(sender.get("card") or "").strip() or None

        return {"type": "reply", "data": reply_payload}

    async def _build_reply_preview_text(self, message_detail: QQPayload) -> Optional[str]:
        """为回复引用构造结构化消息预览文本。

        Args:
            message_detail: ``get_msg`` 返回的消息详情。

        Returns:
            Optional[str]: 基于结构化消息段生成的预览文本；无法生成时返回 ``None``。
        """
        try:
            message_payload = self._require_message_segments(message_detail)
            group_id = str(message_detail.get("group_id") or "").strip()
            # 引用目标可能再次引用自身或另一条消息；预览不继续查询目标详情。
            reply_segments, _ = await self._convert_incoming_segments(
                message_payload, "", group_id, resolve_reply_details=False
            )
        except ValueError:
            return None

        if not reply_segments:
            return None
        return self.build_plain_text(reply_segments)

    def _build_face_text_segment(self, segment_data: Mapping[str, Any]) -> QQSegment:
        """构造 QQ 原生表情文本段。

        支持双模式（移植自 SnowLuma 适配器）：description 转中文描述，
        emoji 转近似 Unicode 表情；未收录的 ID 回退描述表，再回退占位符。

        Args:
            segment_data: OneBot ``face`` 段的 ``data`` 字典。

        Returns:
            QQSegment: 转换后的文本消息段。
        """
        face_id = str(segment_data.get("id", "")).strip()
        face_text = self._resolve_face_text(face_id)
        return self._build_text_segment(face_text)

    def _build_video_text_segment(self, segment_data: Mapping[str, Any]) -> QQSegment:
        """Render video metadata as a readable placeholder without downloading it."""
        name = str(segment_data.get("file_name") or segment_data.get("file") or "视频")
        url = str(segment_data.get("url") or "").strip()
        return self._build_text_segment(f"[视频: {name}{' ' + url if url else ''}]")

    def _build_file_text_segment(self, segment_data: Mapping[str, Any]) -> QQSegment:
        """Render file name and size without implicitly downloading the file."""
        name = str(segment_data.get("name") or segment_data.get("file") or "未知文件")
        size = str(segment_data.get("size") or segment_data.get("file_size") or "").strip()
        return self._build_text_segment(f"[文件: {name}{'，' + size if size else ''}]")

    def _resolve_face_text(self, face_id: str) -> str:
        """按配置的表情解析模式返回表情文本。

        ``description`` 模式输出 ``[小表情·幽灵#187]`` 这类锚点，装 ``emoticon-vision``
        插件后会被替换成 ``[小表情·幽灵：外观描述|情绪|情绪]``；没装插件时锚点自带中文名与
        ID，模型也不会只看到一个占位符。

        Args:
            face_id: QQ 表情 ID。

        Returns:
            str: 解析后的表情文本。
        """
        parse_mode = str(getattr(self._load_settings().plugin, "qq_face_parse_mode", "description") or "description")
        if parse_mode == "emoji" and face_id in QQ_FACE_EMOJIS:
            return str(QQ_FACE_EMOJIS[face_id])
        name = QQ_FACE_DESCRIPTIONS.get(face_id)
        if name:
            return f"[小表情·{name}#{face_id}]"
        logger = getattr(self, "_logger", None)
        if logger is not None:
            logger.debug(f"未收录的 QQ 表情: id={face_id!r} mode={parse_mode}")
        return f"[小表情·未知表情#{face_id}]"

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

    async def _build_forward_segment(self, segment_data: Mapping[str, Any]) -> Optional[QQSegment]:
        """构造合并转发消息段。

        Args:
            segment_data: OneBot ``forward`` 段的 ``data`` 字典。

        Returns:
            Optional[QQSegment]: 转换后的合并转发消息段；失败时返回 ``None``。
        """
        inline_messages = self._extract_forward_messages(segment_data)
        messages = inline_messages

        if messages is None:
            message_id = str(segment_data.get("id") or "").strip()
            if not message_id:
                return None

            forward_detail = await self._query_service.get_forward_message(message_id)
            if forward_detail is None:
                return self._build_text_segment("[forward]")

            messages = self._extract_forward_messages(forward_detail)

        if not isinstance(messages, list):
            return self._build_text_segment("[forward]")

        forward_nodes = await self._build_forward_nodes(messages)
        if not forward_nodes:
            return self._build_text_segment("[forward]")
        return {"type": "forward", "data": forward_nodes}

    def _extract_forward_messages(self, payload: Mapping[str, Any]) -> Optional[List[Any]]:
        """从转发载荷中提取节点列表。

        Args:
            payload: 转发段 ``data`` 或 ``get_forward_msg`` 返回的载荷。

        Returns:
            Optional[List[Any]]: 提取到的节点列表；当载荷中不存在节点列表时返回 ``None``。
        """
        direct_messages = payload.get("messages")
        if isinstance(direct_messages, list):
            return direct_messages

        direct_content = payload.get("content")
        if isinstance(direct_content, list):
            return direct_content

        nested_data = payload.get("data")
        if isinstance(nested_data, Mapping):
            nested_messages = nested_data.get("messages")
            if isinstance(nested_messages, list):
                return nested_messages

            nested_content = nested_data.get("content")
            if isinstance(nested_content, list):
                return nested_content

        return None

    async def _build_forward_nodes(self, messages: List[Any]) -> List[Dict[str, Any]]:
        """将 OneBot 转发节点列表转换为 Host 转发节点列表。

        Args:
            messages: 对端返回的转发节点列表。

        Returns:
            List[Dict[str, Any]]: Host 侧可识别的转发节点列表。
        """
        forward_nodes: List[Dict[str, Any]] = []
        for forward_message in messages:
            if not isinstance(forward_message, Mapping):
                continue

            raw_content = self._extract_forward_node_content(forward_message)
            content_segments = await self._convert_forward_content(raw_content, "")
            sender = self._extract_forward_node_sender(forward_message)

            node_data = forward_message.get("data", {})
            if not isinstance(node_data, Mapping):
                node_data = {}

            forward_nodes.append(
                {
                    "user_id": str(
                        sender.get("user_id")
                        or sender.get("uin")
                        or node_data.get("user_id")
                        or node_data.get("uin")
                        or ""
                    ).strip()
                    or None,
                    "user_nickname": str(
                        sender.get("nickname")
                        or sender.get("name")
                        or node_data.get("nickname")
                        or node_data.get("name")
                        or "未知用户"
                    ),
                    "user_cardname": str(sender.get("card") or node_data.get("card") or "").strip() or None,
                    "message_id": str(
                        forward_message.get("message_id")
                        or forward_message.get("id")
                        or node_data.get("id")
                        or uuid4().hex
                    ),
                    "content": content_segments or [self._build_text_segment("[empty]")],
                }
            )
        return forward_nodes

    def _extract_forward_node_content(self, forward_message: Mapping[str, Any]) -> Any:
        """提取单个转发节点中的消息段列表。

        Args:
            forward_message: 对端返回的单个转发节点。

        Returns:
            Any: 原始消息段列表；不存在时返回空列表。
        """
        direct_content = forward_message.get("content")
        if isinstance(direct_content, list):
            return direct_content

        direct_message = forward_message.get("message")
        if isinstance(direct_message, list):
            return direct_message

        node_data = forward_message.get("data", {})
        if not isinstance(node_data, Mapping):
            return []

        nested_content = node_data.get("content")
        if isinstance(nested_content, list):
            return nested_content

        nested_message = node_data.get("message")
        if isinstance(nested_message, list):
            return nested_message

        return []

    def _extract_forward_node_sender(self, forward_message: Mapping[str, Any]) -> Mapping[str, Any]:
        """提取单个转发节点的发送者信息。

        Args:
            forward_message: 对端返回的单个转发节点。

        Returns:
            Mapping[str, Any]: 归一化后的发送者信息映射。
        """
        sender = forward_message.get("sender", {})
        if isinstance(sender, Mapping):
            return sender

        node_data = forward_message.get("data", {})
        if not isinstance(node_data, Mapping):
            return {}

        normalized_sender: Dict[str, Any] = {}
        user_id = str(node_data.get("user_id") or node_data.get("uin") or "").strip()
        nickname = str(node_data.get("nickname") or node_data.get("name") or "").strip()
        cardname = str(node_data.get("card") or "").strip()
        if user_id:
            normalized_sender["user_id"] = user_id
            normalized_sender["uin"] = user_id
        if nickname:
            normalized_sender["nickname"] = nickname
            normalized_sender["name"] = nickname
        if cardname:
            normalized_sender["card"] = cardname
        return normalized_sender

    async def _convert_forward_content(self, raw_content: Any, self_id: str) -> QQSegments:
        """转换转发节点内部的消息段列表。

        Args:
            raw_content: 转发节点原始内容。
            self_id: 当前机器人账号 ID。

        Returns:
            QQSegments: 转换后的消息段列表。
        """
        if not isinstance(raw_content, list):
            return []

        normalized_segments = self._normalize_incoming_segments(raw_content)
        if not normalized_segments:
            return []

        # 转发节点的引用可能不在当前账号的消息库中，只保留引用 ID。
        segments, _ = await self._convert_incoming_segments(
            normalized_segments, self_id, "", resolve_reply_details=False
        )
        return segments

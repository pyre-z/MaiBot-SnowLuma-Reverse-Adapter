"""Inbound media segment and binary-reference handling."""

from __future__ import annotations

import base64
import hashlib
from binascii import Error as BinasciiError
from pathlib import Path
from typing import Any, Mapping, Optional

from ...types import QQSegment
from ...media.voice import is_wav_voice_binary, transcode_voice_binary_to_wav

class QQInboundMediaMixin:
    async def _build_image_like_segment(
        self,
        segment_data: Mapping[str, Any],
        is_emoji: bool,
    ) -> QQSegment:
        """构造图片或表情消息段。

        媒体取数链（移植自 SnowLuma 适配器）：优先段内 base64，
        其次本地路径，再次 URL 下载，最后 ``get_image`` 动作兜底。

        Args:
            segment_data: OneBot ``image`` 段的 ``data`` 字典。
            is_emoji: 是否按表情组件处理。

        Returns:
            QQSegment: 转换后的图片或表情消息段。
        """
        subtype = self._normalize_numeric_segment_value(segment_data.get("sub_type"))
        actual_is_emoji = is_emoji or (subtype is not None and subtype not in {0, 4, 9})
        emoji_hint = str(segment_data.get("summary") or "").strip()
        if not actual_is_emoji and emoji_hint and emoji_hint != "[图片]":
            actual_is_emoji = True

        binary_data = await self._load_binary_from_segment_data(segment_data, image_action_fallback=True)
        if not binary_data:
            return self._build_text_segment("[emoji]" if actual_is_emoji else "[image]")

        return {
            "type": "emoji" if actual_is_emoji else "image",
            "data": "",
            "hash": hashlib.sha256(binary_data).hexdigest(),
            "binary_data_base64": self._encode_binary(binary_data),
        }

    async def _build_record_segment(self, segment_data: Mapping[str, Any]) -> QQSegment:
        """构造语音消息段。

        画像决定 ``get_record`` 的 out_format：NapCat 要 wav；SnowLuma 要 mp3，
        且服务端可能仍返回 silk。不论拿到什么编码，非 WAV 一律转成合法 WAV ——
        MaiBot 上传时把文件硬编码命名 ``audio.wav``，网关按 WAV 头算时长，
        内容不是 WAV 会直接 500（``invalid wav file``）。

        Args:
            segment_data: OneBot ``record`` 段的 ``data`` 字典。

        Returns:
            QQSegment: 转换后的语音或占位文本消息段。
        """
        file_name = str(segment_data.get("file") or "").strip()
        file_id = str(segment_data.get("file_id") or "").strip() or None
        if not file_name:
            return self._build_text_segment("[voice]")

        out_format = str(self._profile_state.profile.record_out_format or "wav").strip() or "wav"
        record_detail = await self._query_service.get_record_detail(
            file_name=file_name,
            file_id=file_id,
            out_format=out_format,
        )
        if record_detail is None:
            return self._build_text_segment("[voice]")

        record_base64 = str(record_detail.get("base64") or "").strip()
        binary_data: Optional[bytes] = None
        if record_base64:
            try:
                binary_data = self._decode_binary(record_base64)
            except Exception:
                binary_data = None
        if binary_data is None:
            # 部分实现的 get_record 返回本地文件路径而非 base64。
            binary_data = await self._load_binary_reference(str(record_detail.get("file") or "").strip())
        if not binary_data:
            return self._build_text_segment("[voice]")

        if self._profile_state.profile.transcode_silk_voice and not is_wav_voice_binary(binary_data):
            wav_data = await transcode_voice_binary_to_wav(binary_data)
            if wav_data:
                binary_data = wav_data
            else:
                self._logger.warning(
                    "语音转 WAV 失败：请安装插件依赖 silk-python 并确认 ffmpeg 可用，已降级为占位文本"
                )
                return self._build_text_segment("[voice]")

        return {
            "type": "voice",
            "data": "",
            "hash": hashlib.sha256(binary_data).hexdigest(),
            "binary_data_base64": self._encode_binary(binary_data),
        }

    async def _load_binary_from_segment_data(
        self,
        segment_data: Mapping[str, Any],
        *,
        image_action_fallback: bool = False,
    ) -> Optional[bytes]:
        """从消息段字段中按优先级加载媒体二进制。

        取数顺序：``base64`` 字段 → ``base64://`` 引用 → 本地路径 → URL 下载
        →（可选）``get_image`` 动作兜底。

        Args:
            segment_data: 消息段的 ``data`` 字典。
            image_action_fallback: 前序来源全部失败时是否尝试 ``get_image`` 动作。

        Returns:
            Optional[bytes]: 加载到的二进制内容；全部失败时返回 ``None``。
        """
        inline_base64 = str(segment_data.get("base64") or "").strip()
        if inline_base64:
            try:
                return self._decode_binary(inline_base64)
            except Exception:
                pass

        for reference in (segment_data.get("file"), segment_data.get("url")):
            binary_data = await self._load_binary_reference(str(reference or "").strip())
            if binary_data:
                return binary_data

        if image_action_fallback:
            file_identifier = str(segment_data.get("file") or segment_data.get("file_id") or "").strip()
            if file_identifier:
                image_detail = await self._query_service.get_image(file_identifier)
                if isinstance(image_detail, Mapping):
                    for reference in (image_detail.get("file"), image_detail.get("url")):
                        binary_data = await self._load_binary_reference(str(reference or "").strip())
                        if binary_data:
                            return binary_data
        return None

    async def _load_binary_reference(self, reference: str) -> Optional[bytes]:
        """加载一个媒体引用（base64://、本地路径或 URL）。

        Args:
            reference: 媒体引用字符串。

        Returns:
            Optional[bytes]: 加载到的二进制内容；引用为空或加载失败时返回 ``None``。
        """
        if not reference:
            return None

        if reference.startswith("base64://"):
            try:
                return base64.b64decode(reference[len("base64://"):], validate=False)
            except (BinasciiError, ValueError):
                return None

        if reference.startswith("http://") or reference.startswith("https://"):
            return await self._query_service.download_binary(reference)

        candidate_path = Path(reference)
        if candidate_path.is_file():
            try:
                return candidate_path.read_bytes()
            except OSError:
                return None
        return None


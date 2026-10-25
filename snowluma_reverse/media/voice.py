"""语音转码：任意 QQ 语音编码 → WAV（silk/mp3 → PCM → RIFF 容器）。

SnowLuma 的 ``get_record`` 返回 silk 编码语音（magic 头 ``#!SILK_V3``），
部分实现会返回 mp3。MaiBot 的语音识别工具把上传文件**硬编码命名为
``audio.wav``**，而网关（new-api）按 WAV 头计算音频时长以折算计费 token，
内容不是真 WAV 时会直接 500：

    error getting audio duration: invalid wav file (code: count_token_failed)

所以这里统一产出 **合法 WAV**（RIFF/PCM 16bit 单声道 24kHz）：

- silk → pysilk 解码为 PCM，再用 ``wave`` 模块套 RIFF 头，**不依赖 ffmpeg**；
- 其他非 WAV 编码（mp3/amr 等）→ ffmpeg 落到临时文件再读回
  （写管道会让 RIFF 长度字段无法回填，生产出网关读不出时长的残缺头）。

依赖缺失或转码失败时返回 ``None``，由上层记录警告并降级为占位文本。
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from shutil import which
from tempfile import TemporaryDirectory
from typing import Optional

import asyncio
import subprocess
import wave

VOICE_TRANSCODE_SAMPLE_RATE = 24000
VOICE_TRANSCODE_CHANNELS = 1
VOICE_TRANSCODE_SAMPLE_WIDTH = 2
VOICE_TRANSCODE_TIMEOUT_SECONDS = 30.0

_SILK_MAGIC_PREFIXES = (b"#!SILK_V3", b"\x02#!SILK_V3")


def is_silk_voice_binary(data: bytes) -> bool:
    """按 magic 头判断二进制是否为 silk 编码语音。

    Args:
        data: 语音二进制内容。

    Returns:
        bool: 若为 silk 编码则返回 ``True``。
    """
    return data.startswith(_SILK_MAGIC_PREFIXES)


def is_wav_voice_binary(data: bytes) -> bool:
    """按 RIFF 头判断二进制是否已是 WAV。

    Args:
        data: 语音二进制内容。

    Returns:
        bool: 若为 ``RIFF....WAVE`` 结构则返回 ``True``。
    """
    return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE"


def pcm_to_wav_binary(
    pcm_data: bytes,
    sample_rate: int = VOICE_TRANSCODE_SAMPLE_RATE,
    channels: int = VOICE_TRANSCODE_CHANNELS,
    sample_width: int = VOICE_TRANSCODE_SAMPLE_WIDTH,
) -> bytes:
    """把裸 PCM 套成完整 WAV 容器。

    Args:
        pcm_data: s16le 裸 PCM 数据。
        sample_rate: 采样率。
        channels: 声道数。
        sample_width: 每样本字节数（2 = 16bit）。

    Returns:
        bytes: 带完整 RIFF 头（含正确长度字段）的 WAV 二进制。
    """
    buffer = BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(channels)
        writer.setsampwidth(sample_width)
        writer.setframerate(sample_rate)
        writer.writeframes(pcm_data)
    return buffer.getvalue()


def _decode_silk_to_pcm_sync(data: bytes, sample_rate: int = VOICE_TRANSCODE_SAMPLE_RATE) -> bytes:
    """同步解码 silk 为 PCM（s16le/单声道）。

    Args:
        data: silk 二进制内容。
        sample_rate: 目标采样率。

    Returns:
        bytes: PCM 二进制；pysilk 未安装或解码失败时返回空字节串。
    """
    try:
        from importlib import import_module

        pysilk = import_module("pysilk")
    except ImportError:
        return b""

    output_buffer = BytesIO()
    try:
        pysilk.decode(BytesIO(data), output_buffer, sample_rate)
    except Exception:
        return b""
    return output_buffer.getvalue()


async def _ffmpeg_to_wav_binary(data: bytes) -> Optional[bytes]:
    """用 ffmpeg 把任意音频转成 WAV（落临时文件以获得完整 RIFF 头）。

    Args:
        data: 原始音频二进制。

    Returns:
        Optional[bytes]: WAV 二进制；ffmpeg 缺失、输出为空或超时返回 ``None``。
    """
    ffmpeg_path = which("ffmpeg")
    if not ffmpeg_path:
        return None

    with TemporaryDirectory(prefix="snowluma-voice-") as workdir:
        source_path = Path(workdir) / "input.bin"
        target_path = Path(workdir) / "output.wav"
        source_path.write_bytes(data)
        process = await asyncio.create_subprocess_exec(
            ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source_path),
            "-ac",
            str(VOICE_TRANSCODE_CHANNELS),
            "-ar",
            str(VOICE_TRANSCODE_SAMPLE_RATE),
            "-c:a",
            "pcm_s16le",
            "-f",
            "wav",
            str(target_path),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            await asyncio.wait_for(process.wait(), timeout=VOICE_TRANSCODE_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            process.kill()
            return None
        except asyncio.CancelledError:
            process.kill()
            raise

        if process.returncode != 0 or not target_path.exists():
            return None
        wav_data = target_path.read_bytes()
    return wav_data or None


async def transcode_voice_binary_to_wav(data: bytes) -> Optional[bytes]:
    """把语音二进制统一转成合法 WAV。

    Args:
        data: 语音二进制内容（silk / mp3 / amr / wav 等）。

    Returns:
        Optional[bytes]: WAV 二进制；输入为空或全部转码路径失败时返回 ``None``。
    """
    if not data:
        return None
    if is_wav_voice_binary(data):
        return data

    if is_silk_voice_binary(data):
        pcm_data = await asyncio.to_thread(_decode_silk_to_pcm_sync, data)
        if pcm_data:
            return pcm_to_wav_binary(pcm_data)
        # pysilk 缺失或解码失败时退回 ffmpeg（ffmpeg 自带 silk 解码器通常不可用，仅作兜底）
        return await _ffmpeg_to_wav_binary(data)

    return await _ffmpeg_to_wav_binary(data)

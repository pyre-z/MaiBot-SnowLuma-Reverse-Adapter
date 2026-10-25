"""语音转码单测：确保送给 MaiBot 的永远是合法 WAV。

关键回归点：MaiBot 把语音上传文件硬编码命名为 ``audio.wav``，网关按 WAV 头
算时长，只要内容不是真 WAV 就会 500（``invalid wav file``）。此前 silk 被转成
MP3，线上 8 条语音全挂。
"""

from __future__ import annotations

import shutil
import struct
import subprocess
import sys
import wave
from io import BytesIO
from pathlib import Path

import pytest

from snowluma_reverse.media.voice import (
    VOICE_TRANSCODE_SAMPLE_RATE,
    is_wav_voice_binary,
    pcm_to_wav_binary,
    transcode_voice_binary_to_wav,
)

_PCM_FIXTURE_SECONDS = 1.0


def _sine_pcm(seconds: float = _PCM_FIXTURE_SECONDS, freq: float = 440.0) -> bytes:
    """生成 s16le / 24kHz / 单声道正弦波 PCM。"""
    frames = int(VOICE_TRANSCODE_SAMPLE_RATE * seconds)
    samples = []
    for index in range(frames):
        t = index / VOICE_TRANSCODE_SAMPLE_RATE
        value = int(12000 * (1 if int(t * freq * 2) % 2 == 0 else -1))
        samples.append(struct.pack("<h", value))
    return b"".join(samples)


def _wav_duration(data: bytes) -> float:
    """用标准库读 WAV 时长（顺带证明 RIFF 头合法）。"""
    with wave.open(BytesIO(data), "rb") as reader:
        assert reader.getsampwidth() == 2
        return reader.getnframes() / reader.getframerate()


def test_pcm_to_wav_is_valid_riff():
    wav_data = pcm_to_wav_binary(_sine_pcm())
    assert is_wav_voice_binary(wav_data)
    assert wav_data[:4] == b"RIFF" and wav_data[8:12] == b"WAVE"
    # RIFF 长度字段必须是回填过的真实值，否则网关读不出时长
    assert struct.unpack("<I", wav_data[4:8])[0] == len(wav_data) - 8
    assert _wav_duration(wav_data) == pytest.approx(_PCM_FIXTURE_SECONDS, abs=0.01)


@pytest.mark.asyncio
async def test_wav_passes_through_untouched():
    wav_data = pcm_to_wav_binary(_sine_pcm())
    assert await transcode_voice_binary_to_wav(wav_data) == wav_data


@pytest.mark.asyncio
async def test_mp3_is_converted_to_wav(tmp_path: Path):
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg 不可用")
    wav_path = tmp_path / "src.wav"
    mp3_path = tmp_path / "src.mp3"
    wav_path.write_bytes(pcm_to_wav_binary(_sine_pcm()))
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(wav_path), "-c:a", "libmp3lame", str(mp3_path)],
        check=True,
    )
    mp3_data = mp3_path.read_bytes()
    assert mp3_data[:4] != b"RIFF"

    converted = await transcode_voice_binary_to_wav(mp3_data)
    assert converted is not None
    assert is_wav_voice_binary(converted)
    assert _wav_duration(converted) == pytest.approx(_PCM_FIXTURE_SECONDS, abs=0.2)


@pytest.mark.asyncio
async def test_silk_is_converted_to_wav():
    pysilk = pytest.importorskip("pysilk", reason="宿主需装 silk-python 才能覆盖 silk 分支")
    pcm_data = _sine_pcm()
    silk_buffer = BytesIO()
    pysilk.encode(BytesIO(pcm_data), silk_buffer, VOICE_TRANSCODE_SAMPLE_RATE, 1, 10)
    silk_data = silk_buffer.getvalue()
    assert silk_data.startswith(b"#!SILK_V3")

    converted = await transcode_voice_binary_to_wav(silk_data)
    assert converted is not None
    assert is_wav_voice_binary(converted)
    assert _wav_duration(converted) == pytest.approx(_PCM_FIXTURE_SECONDS, abs=0.1)


@pytest.mark.asyncio
async def test_empty_input_returns_none():
    assert await transcode_voice_binary_to_wav(b"") is None

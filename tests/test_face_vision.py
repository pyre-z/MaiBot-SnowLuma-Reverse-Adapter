"""表情视觉描述：存储层、运行时 worker 与 VLM 配置解析的单测（全部离线）。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from snowluma_reverse.media.face_vision_assets import (
    build_messages,
    clean_description,
    resolve_vlm_target,
)
from snowluma_reverse.media.face_vision_store import FaceVisionStore
from snowluma_reverse.media.face_vision_worker import FaceVisionWorker, UnsatisfiableFace


class FakeLogger:
    """收集日志，便于断言。"""

    def __init__(self) -> None:
        self.records: list[tuple[str, str]] = []

    def info(self, message: str, *args: Any, **kwargs: Any) -> None:
        self.records.append(("info", message))

    def warning(self, message: str, *args: Any, **kwargs: Any) -> None:
        self.records.append(("warning", message))

    def debug(self, message: str, *args: Any, **kwargs: Any) -> None:
        self.records.append(("debug", message))

    def error(self, message: str, *args: Any, **kwargs: Any) -> None:
        self.records.append(("error", message))


def _write_table(path: Path, faces: dict[str, dict[str, Any]]) -> None:
    path.write_text(json.dumps({"meta": {"count": len(faces)}, "faces": faces}, ensure_ascii=False), encoding="utf-8")


# --------------------------------------------------------------------------- #
# 存储层
# --------------------------------------------------------------------------- #
def test_store_overlay_wins_and_persists(tmp_path: Path) -> None:
    builtin = tmp_path / "builtin.json"
    _write_table(builtin, {"187": {"name": "幽灵", "desc": "内置描述"}})

    store = FaceVisionStore(builtin)
    store.attach_overlay(tmp_path / "runtime")
    assert store.describe("187") == "[QQ小表情·幽灵｜内置描述]"

    store.put("203", {"name": "托脸", "desc": "白熊双手托腮发呆"})
    store.put("187", {"name": "幽灵", "desc": "运行时描述"})
    assert store.describe("187") == "[QQ小表情·幽灵｜运行时描述]"
    assert store.describe("203") == "[QQ小表情·托脸｜白熊双手托腮发呆]"

    saved = json.loads((tmp_path / "runtime" / "face_vision_runtime.json").read_text(encoding="utf-8"))
    assert set(saved["faces"]) == {"187", "203"}
    assert store.stats() == {"builtin": 1, "runtime": 2}


def test_store_ignores_empty_description(tmp_path: Path) -> None:
    builtin = tmp_path / "builtin.json"
    _write_table(builtin, {})
    store = FaceVisionStore(builtin)
    store.attach_overlay(tmp_path / "runtime")

    store.put("1", {"name": "惊讶", "desc": "   "})
    assert store.describe("1") is None
    assert not (tmp_path / "runtime" / "face_vision_runtime.json").exists()


# --------------------------------------------------------------------------- #
# VLM 配置解析
# --------------------------------------------------------------------------- #
def test_resolve_vlm_target_reads_default_vision_model(tmp_path: Path) -> None:
    config = tmp_path / "model_config.toml"
    config.write_text(
        """
[[models]]
model_identifier = "gemini-3.8-flash"
model_type = "llm"
name = "gemini-3.8-flash"
api_provider = "PyreGate"
visual = true

[[api_providers]]
name = "PyreGate"
base_url = "https://api.example.com/v1"
api_key = "sk-test"
client_type = "openai"

[model_task_config.vlm]
model_list = ["gemini-3.8-flash"]
""",
        encoding="utf-8",
    )
    assert resolve_vlm_target(config) == ("https://api.example.com/v1", "sk-test", "gemini-3.8-flash")


def test_resolve_vlm_target_skips_non_openai_provider(tmp_path: Path) -> None:
    config = tmp_path / "model_config.toml"
    config.write_text(
        """
[[models]]
model_identifier = "gemini-native"
name = "gemini-native"
api_provider = "NativeGemini"

[[models]]
model_identifier = "qwen-vl"
name = "qwen-vl"
api_provider = "OpenAI Like"

[[api_providers]]
name = "NativeGemini"
base_url = "https://api.example.com/v1beta"
api_key = "sk-a"
client_type = "gemini"

[[api_providers]]
name = "OpenAI Like"
base_url = "https://api.example.com/v1"
api_key = "sk-b"
client_type = "openai"

[model_task_config.vlm]
model_list = ["gemini-native", "qwen-vl"]
""",
        encoding="utf-8",
    )
    assert resolve_vlm_target(config) == ("https://api.example.com/v1", "sk-b", "qwen-vl")


# --------------------------------------------------------------------------- #
# worker
# --------------------------------------------------------------------------- #
def test_worker_build_entry_uses_combined_images(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = FaceVisionStore(tmp_path / "builtin.json")
    store.attach_overlay(tmp_path / "runtime")
    logger = FakeLogger()
    worker = FaceVisionWorker(store, tmp_path, logger, model_config_path=str(tmp_path / "m.toml"),
                              desc_max_chars=20)
    monkeypatch.setattr(worker, "_ensure_index", lambda: {"187": {"emojiId": "187", "describe": "/幽灵"}})
    monkeypatch.setattr(
        "snowluma_reverse.media.face_vision_worker.collect_images",
        lambda entry, cache_dir, combine=True: [(b"png", "qface-png"), (b"gif", "qzone-gif")],
    )
    captured: dict[str, Any] = {}

    def fake_post(base_url, api_key, model, messages):
        captured["messages"] = messages
        return "白色小幽灵上下漂浮眨眼"

    worker._vlm = lambda: ("https://api.example.com/v1", "sk-test", "gemini-3.8-flash")  # type: ignore[method-assign]
    monkeypatch.setattr(worker, "_post_vlm", fake_post)

    entry = worker._build_entry("187")
    assert entry["name"] == "幽灵"
    assert entry["desc"] == "白色小幽灵上下漂浮眨眼"
    assert entry["sources"] == ["qface-png", "qzone-gif"]
    assert entry["model"] == "gemini-3.8-flash"
    text_prompt = captured["messages"][0]["content"][0]["text"]
    assert "静态图" in text_prompt and "幽灵" in text_prompt


def test_worker_build_entry_rejects_unknown_face(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = FaceVisionStore(tmp_path / "builtin.json")
    store.attach_overlay(tmp_path / "runtime")
    worker = FaceVisionWorker(store, tmp_path, FakeLogger())
    monkeypatch.setattr(worker, "_ensure_index", lambda: {})
    with pytest.raises(UnsatisfiableFace):
        worker._build_entry("424242")


@pytest.mark.asyncio
async def test_worker_generates_once_and_skips_known(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = FaceVisionStore(tmp_path / "builtin.json")
    store.attach_overlay(tmp_path / "runtime")
    worker = FaceVisionWorker(store, tmp_path, FakeLogger(), max_attempts=1)
    calls: list[str] = []

    def fake_build(face_id: str) -> dict[str, Any]:
        calls.append(face_id)
        return {"name": "新表情", "desc": "一个新表情", "sources": ["qface-png"], "model": "m"}

    monkeypatch.setattr(worker, "_build_entry", fake_build)
    await worker.start()
    worker.request("9001")
    worker.request("9001")  # 重复入队应被去重
    await asyncio.wait_for(worker._queue.join(), timeout=2)
    await worker.stop()

    assert calls == ["9001"]
    assert store.describe("9001") == "[QQ小表情·新表情｜一个新表情]"

    worker.request("9001")
    assert worker._queue.qsize() == 0


def test_worker_request_is_noop_before_start(tmp_path: Path) -> None:
    store = FaceVisionStore(tmp_path / "builtin.json")
    worker = FaceVisionWorker(store, tmp_path, FakeLogger())
    worker.request("187")
    assert worker._queue.qsize() == 0


# --------------------------------------------------------------------------- #
# 提示词与清洗
# --------------------------------------------------------------------------- #
def test_build_messages_marks_two_image_sources() -> None:
    messages = build_messages("幽灵", [(b"a", "qface-png"), (b"b", "qzone-gif")])
    content = messages[0]["content"]
    assert len(content) == 3
    assert "第一张是它的静态图" in content[0]["text"]
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_clean_description_strips_preamble_and_caps() -> None:
    assert clean_description("这是一张黄色的笑脸。") == "黄色的笑脸"
    assert len(clean_description("字" * 100, 10)) == 10

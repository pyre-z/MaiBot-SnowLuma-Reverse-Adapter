"""禁言状态存储路径回归测试。"""

from __future__ import annotations

import json
import logging

import pytest

pytest.importorskip("maibot_sdk")

from snowluma_reverse.services.ban_state_store import QQBanStateStore, QQBanRecord


def _write(payload_path, records):
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload_path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")


@pytest.mark.asyncio
async def test_store_uses_injected_data_dir(tmp_path):
    """注入统一数据目录时，状态文件落在该目录而不是插件源码目录。"""

    storage = tmp_path / "napcat_adapter" / "ban_state.json"
    store = QQBanStateStore(logging.getLogger("test"), storage_path=storage)

    assert store.storage_path == storage
    await store.upsert(QQBanRecord(group_id="123", user_id="456", lift_time=1700000000))

    assert storage.exists()
    payload = json.loads(storage.read_text(encoding="utf-8"))
    assert payload == [{"group_id": "123", "user_id": "456", "lift_time": 1700000000}]


@pytest.mark.asyncio
async def test_store_migrates_legacy_file(tmp_path, monkeypatch):
    """旧式源码目录里已有数据时，读取后立即写入统一目录。"""

    legacy = tmp_path / "legacy" / "ban_state.json"
    _write(legacy, [{"group_id": "1", "user_id": "2", "lift_time": -1}])
    monkeypatch.setattr(
        "snowluma_reverse.services.ban_state_store._LEGACY_STORAGE_PATH",
        legacy,
    )

    storage = tmp_path / "unified" / "ban_state.json"
    store = QQBanStateStore(logging.getLogger("test"), storage_path=storage)
    await store.load()

    assert [record.record_key for record in await store.snapshot()] == ["1:2"]
    assert storage.exists(), "旧数据应迁移到统一目录"
    assert json.loads(storage.read_text(encoding="utf-8"))[0]["group_id"] == "1"


@pytest.mark.asyncio
async def test_store_falls_back_to_legacy_path(tmp_path, monkeypatch):
    """未注入数据目录时保持旧行为，避免旧版 SDK 下丢状态。"""

    legacy = tmp_path / "legacy" / "ban_state.json"
    monkeypatch.setattr(
        "snowluma_reverse.services.ban_state_store._LEGACY_STORAGE_PATH",
        legacy,
    )

    store = QQBanStateStore(logging.getLogger("test"))

    assert store.storage_path == legacy

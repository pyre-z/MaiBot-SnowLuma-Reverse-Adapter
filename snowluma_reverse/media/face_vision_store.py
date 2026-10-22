"""QQ 表情描述表：包内置快照 + 运行时补写层（overlay）。

- 包内置：``snowluma_reverse/data/face_vision.json``（离线脚本全量生成，随仓库走）；
- 运行时：``<插件数据目录>/face_vision_runtime.json``（遇到新表情时补写，持久且不污染仓库）。

读取时 overlay 优先，写入只在 overlay 层，升级/重建插件不会丢已生成的描述。
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

BUILTIN_TABLE = Path(__file__).resolve().parent.parent / "data" / "face_vision.json"
RUNTIME_TABLE_NAME = "face_vision_runtime.json"


def _read_faces(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    faces = payload.get("faces") if isinstance(payload, dict) else None
    return faces if isinstance(faces, dict) else {}


class FaceVisionStore:
    """只读内置表 + 可写的运行时叠加层。"""

    def __init__(self, builtin_path: Path = BUILTIN_TABLE) -> None:
        self._builtin_path = builtin_path
        self._builtin = _read_faces(builtin_path)
        self._overlay: Dict[str, Dict[str, Any]] = {}
        self._overlay_path: Optional[Path] = None
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ 生命周期
    def attach_overlay(self, directory: Path) -> None:
        """挂载运行时数据目录；已有内容会被载入，读取时覆盖内置表。"""
        path = Path(directory) / RUNTIME_TABLE_NAME
        with self._lock:
            self._overlay_path = path
            self._overlay = _read_faces(path)

    def reload(self) -> None:
        """重新读取内置表与叠加层（离线脚本补生成后调用）。"""
        with self._lock:
            self._builtin = _read_faces(self._builtin_path)
            if self._overlay_path is not None:
                self._overlay = _read_faces(self._overlay_path)

    # ------------------------------------------------------------------ 读取
    def get(self, face_id: str) -> Optional[Dict[str, Any]]:
        key = str(face_id).strip()
        with self._lock:
            entry = self._overlay.get(key)
            if isinstance(entry, dict) and entry.get("desc"):
                return entry
            entry = self._builtin.get(key)
            return entry if isinstance(entry, dict) else None

    def has(self, face_id: str) -> bool:
        entry = self.get(face_id)
        return bool(entry and entry.get("desc"))

    def describe(self, face_id: str) -> Optional[str]:
        """渲染成注入给模型的文本；无描述时返回 ``None``。"""
        entry = self.get(face_id)
        if not entry:
            return None
        desc = str(entry.get("desc") or "").strip()
        if not desc:
            return None
        name = str(entry.get("name") or "").strip()
        return f"[QQ小表情·{name}｜{desc}]" if name else f"[QQ小表情｜{desc}]"

    # ------------------------------------------------------------------ 写入
    def put(self, face_id: str, entry: Dict[str, Any]) -> None:
        """写入叠加层并立即落盘（原子替换）。"""
        key = str(face_id).strip()
        if not key or not isinstance(entry, dict):
            return
        entry = {**entry, "desc": str(entry.get("desc") or "").strip()}
        if not entry["desc"]:
            return
        with self._lock:
            self._overlay[key] = entry
            self._save_locked()

    def _save_locked(self) -> None:
        if self._overlay_path is None:
            return
        payload = {
            "meta": {
                "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                "source": "runtime",
                "count": len(self._overlay),
            },
            "faces": dict(sorted(self._overlay.items(), key=lambda item: str(item[0]))),
        }
        path = self._overlay_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temp, path)

    # ------------------------------------------------------------------ 统计
    def stats(self) -> Dict[str, int]:
        with self._lock:
            return {"builtin": len(self._builtin), "runtime": len(self._overlay)}


STORE = FaceVisionStore()

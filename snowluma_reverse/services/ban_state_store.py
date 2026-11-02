"""禁言状态存储。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

import asyncio
import json


_LEGACY_STORAGE_PATH = Path(__file__).resolve().parents[2] / "data" / "napcat_adapter" / "ban_state.json"
"""旧式存储位置：插件源码目录下的 ``data/``。仅在未注入统一数据目录时兜底使用。"""


@dataclass
class QQBanRecord:
    """禁言记录。"""

    group_id: str
    user_id: str
    lift_time: int

    @property
    def record_key(self) -> str:
        """返回当前记录的稳定键。

        Returns:
            str: 由群号和用户号拼接得到的稳定键。
        """
        return f"{self.group_id}:{self.user_id}"

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> Optional["QQBanRecord"]:
        """从字典构造禁言记录。

        Args:
            payload: 原始记录字典。

        Returns:
            Optional[QQBanRecord]: 构造成功时返回记录对象，否则返回 ``None``。
        """
        group_id = str(payload.get("group_id") or "").strip()
        user_id = str(payload.get("user_id") or "").strip()
        if not group_id or not user_id:
            return None

        try:
            lift_time = int(payload.get("lift_time", -1))
        except (TypeError, ValueError):
            lift_time = -1
        return cls(group_id=group_id, user_id=user_id, lift_time=lift_time)

    def to_dict(self) -> Dict[str, Any]:
        """将记录转换为可序列化字典。

        Returns:
            Dict[str, Any]: 可直接写入 JSON 的记录字典。
        """
        return asdict(self)


class QQBanStateStore:
    """禁言状态持久化仓库。"""

    def __init__(self, logger: Any, storage_path: Optional[Path] = None) -> None:
        """初始化禁言状态仓库。

        Args:
            logger: 插件日志对象。
            storage_path: 持久化文件路径；不传时回落到插件源码目录的 ``data/``（兼容旧部署）。
        """

        self._logger = logger
        self._storage_path = Path(storage_path) if storage_path else _LEGACY_STORAGE_PATH
        self._records: Dict[str, QQBanRecord] = {}
        self._records_lock = asyncio.Lock()

    @property
    def storage_path(self) -> Path:
        """返回当前生效的持久化路径，便于排查数据落点。"""

        return self._storage_path

    def _resolve_load_path(self) -> Optional[Path]:
        """选择本次加载的文件，同时把旧式源码目录的数据迁到统一目录。

        Returns:
            Optional[Path]: 可读取的文件路径；不存在时返回 ``None``。
        """

        if self._storage_path.exists():
            return self._storage_path
        if self._storage_path == _LEGACY_STORAGE_PATH or not _LEGACY_STORAGE_PATH.exists():
            return None
        # 已注入统一数据目录：旧文件还在源码目录里，读出来随后由 persist() 写到新位置。
        self._logger.info(
            f"检测到旧式禁言状态文件 {_LEGACY_STORAGE_PATH}，将迁移到 {self._storage_path}"
        )
        return _LEGACY_STORAGE_PATH

    async def load(self) -> None:
        """从本地文件加载禁言记录。"""

        source_path = self._resolve_load_path()
        if source_path is None:
            return

        try:
            raw_payload = json.loads(source_path.read_text(encoding="utf-8"))
        except Exception as exc:
            self._logger.warning(f"禁言状态文件读取失败，将忽略旧记录: {exc}")
            return

        if not isinstance(raw_payload, list):
            self._logger.warning("禁言状态文件格式非法，将忽略旧记录")
            return

        loaded_records: Dict[str, QQBanRecord] = {}
        for item in raw_payload:
            if not isinstance(item, Mapping):
                continue
            record = QQBanRecord.from_mapping(item)
            if record is not None:
                loaded_records[record.record_key] = record

        async with self._records_lock:
            self._records = loaded_records
        if loaded_records:
            self._logger.info(f"禁言状态已加载 {len(loaded_records)} 条记录")
        if source_path != self._storage_path:
            # 从旧式目录读到的内容立即落到统一目录，下次启动不再依赖源码目录。
            await self.persist()

    async def snapshot(self) -> List[QQBanRecord]:
        """返回当前记录快照。

        Returns:
            List[QQBanRecord]: 当前内存中的记录列表副本。
        """
        async with self._records_lock:
            return list(self._records.values())

    async def upsert(self, record: QQBanRecord) -> None:
        """新增或更新一条禁言记录。

        Args:
            record: 待写入的禁言记录。
        """
        async with self._records_lock:
            self._records[record.record_key] = record
        await self.persist()

    async def remove(self, group_id: str, user_id: str) -> Optional[QQBanRecord]:
        """删除指定禁言记录。

        Args:
            group_id: 群号。
            user_id: 用户号。

        Returns:
            Optional[QQBanRecord]: 被移除的记录；不存在时返回 ``None``。
        """
        record_key = f"{group_id}:{user_id}"
        return await self.pop(record_key)

    async def pop(self, record_key: str) -> Optional[QQBanRecord]:
        """按稳定键移除一条记录。

        Args:
            record_key: 记录稳定键。

        Returns:
            Optional[QQBanRecord]: 被移除的记录；不存在时返回 ``None``。
        """
        async with self._records_lock:
            removed_record = self._records.pop(record_key, None)
        if removed_record is not None:
            await self.persist()
        return removed_record

    async def persist(self) -> None:
        """将当前禁言记录持久化到本地文件。"""
        async with self._records_lock:
            serialized_records = [
                record.to_dict() for record in sorted(self._records.values(), key=lambda item: item.record_key)
            ]

        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            self._storage_path.write_text(
                json.dumps(serialized_records, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            self._logger.warning(f"禁言状态持久化失败: {exc}")

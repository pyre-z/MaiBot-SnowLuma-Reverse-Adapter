"""运行时补描述：遇到描述表里没有的 QQ 表情，后台下载素材并用默认 VLM 生成描述。

设计要点（都是有意的）：

- **不阻塞消息**：``request()`` 只入队，当前消息按 ``emoji → [中文名] → [表情]`` 回退渲染，
  首条消息拿不到描述是可接受的代价，换来零额外延迟。
- **复用 MaiBot 默认 VLM**：从容器内 ``/MaiMBot/config/model_config.toml`` 解析
  ``[model_task_config.vlm]`` 第一个 OpenAI 兼容模型及其 Provider 密钥，
  主人在 WebUI 换视觉模型时自动跟随，不另存一份 key。
- **单并发 + 去重 + 重试上限**：同一 id 只会跑一次，失败最多重试 ``max_attempts`` 次，
  素材或索引里根本没有的表情直接跳过，不反复烧钱。
- **落 overlay 不落仓库**：结果写插件数据目录，升级重建不丢。
"""

from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from .face_vision_assets import (
    DESC_MAX_CHARS,
    INDEX_URL,
    build_messages,
    clean_description,
    collect_images,
    load_index,
    resolve_vlm_target,
)
from .face_vision_store import FaceVisionStore

MODEL_CONFIG_CANDIDATES = (
    "/MaiMBot/config/model_config.toml",
    "config/model_config.toml",
)


class UnsatisfiableFace(Exception):
    """素材或索引里没有这个表情，重试也没意义。"""


class FaceVisionWorker:
    """单并发后台队列，为未知表情补生成描述。"""

    def __init__(
        self,
        store: FaceVisionStore,
        data_dir: Path,
        logger: Any,
        *,
        enabled: bool = True,
        index_url: str = INDEX_URL,
        index_refresh_hours: float = 24.0,
        desc_max_chars: int = DESC_MAX_CHARS,
        max_attempts: int = 2,
        timeout_s: float = 90.0,
        model_config_path: str = "",
        queue_size: int = 64,
    ) -> None:
        self._store = store
        self._data_dir = Path(data_dir)
        self._logger = logger
        self._enabled = bool(enabled)
        self._index_url = index_url
        self._index_refresh_hours = float(index_refresh_hours)
        self._desc_max_chars = int(desc_max_chars)
        self._max_attempts = max(1, int(max_attempts))
        self._timeout_s = float(timeout_s)
        self._model_config_path = str(model_config_path or "")
        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=max(1, queue_size))
        self._task: Optional[asyncio.Task] = None
        self._inflight: set[str] = set()
        self._pending: set[str] = set()
        self._attempts: Dict[str, int] = {}
        self._skipped: set[str] = set()
        self._index_cache: Optional[Dict[str, Dict[str, Any]]] = None
        self._vlm_cache: Optional[tuple[str, str, str]] = None
        self._vlm_error: Optional[str] = None

    # ------------------------------------------------------------------ 生命周期
    async def start(self) -> None:
        if self._task is not None or not self._enabled:
            return
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._task = asyncio.create_task(self._loop(), name="face-vision-worker")
        self._logger.info("[表情描述] 运行时补描述已启动（复用 MaiBot 默认 VLM）")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001 - 关闭阶段忽略一切
            pass
        self._task = None

    def reconfigure(self, **kwargs: Any) -> None:
        """配置热更新：只改参数，队列与已生成的描述保留。"""
        for key, value in kwargs.items():
            if value is None:
                continue
            if key == "enabled":
                self._enabled = bool(value)
            elif key == "desc_max_chars":
                self._desc_max_chars = int(value)
            elif key == "max_attempts":
                self._max_attempts = max(1, int(value))
            elif key == "timeout_s":
                self._timeout_s = float(value)
            elif key == "index_refresh_hours":
                self._index_refresh_hours = float(value)
            elif key == "index_url":
                self._index_url = str(value)
            elif key == "model_config_path":
                self._model_config_path = str(value)
                self._vlm_cache = None
                self._vlm_error = None

    # ------------------------------------------------------------------ 入队
    def request(self, face_id: str) -> None:
        """把未知表情投进队列；任何异常都不应影响消息处理。"""
        if not self._enabled or self._task is None:
            return
        key = str(face_id).strip()
        if not key or self._store.has(key):
            return
        if key in self._inflight or key in self._pending or key in self._skipped:
            return
        if self._attempts.get(key, 0) >= self._max_attempts:
            return
        try:
            self._queue.put_nowait(key)
        except asyncio.QueueFull:
            self._logger.debug("[表情描述] 队列已满，丢弃本次请求")
            return
        self._pending.add(key)

    # ------------------------------------------------------------------ 队列循环
    async def _loop(self) -> None:
        while True:
            face_id = await self._queue.get()
            self._inflight.add(face_id)
            try:
                entry = await asyncio.to_thread(self._build_entry, face_id)
            except UnsatisfiableFace as error:
                self._skipped.add(face_id)
                self._logger.info(f"[表情描述] 跳过 {face_id}：{error}")
            except Exception as error:  # noqa: BLE001 - 单条失败不能拖垮 worker
                self._attempts[face_id] = self._attempts.get(face_id, 0) + 1
                self._logger.warning(
                    f"[表情描述] 生成失败 {face_id}（第 {self._attempts[face_id]}/{self._max_attempts} 次）：{error}"
                )
            else:
                self._store.put(face_id, entry)
                self._logger.info(
                    f"[表情描述] 已生成 {face_id} {entry.get('name')} ← {'+'.join(entry.get('sources', []))}：{entry.get('desc')}"
                )
            finally:
                self._inflight.discard(face_id)
                self._pending.discard(face_id)
                self._queue.task_done()

    # ------------------------------------------------------------------ 生成
    def _build_entry(self, face_id: str) -> Dict[str, Any]:
        index = self._ensure_index()
        raw_entry = index.get(str(face_id).strip())
        if not raw_entry:
            raise UnsatisfiableFace("QFace 索引里没有该表情（腾讯新增，等索引更新）")
        name = str(raw_entry.get("describe") or "").lstrip("/").strip() or f"表情{face_id}"
        images = collect_images(raw_entry, self._data_dir)
        if not images:
            raise UnsatisfiableFace("静态图与动作帧都取不到")
        base_url, api_key, model = self._vlm()
        messages = build_messages(name, images, self._desc_max_chars)
        desc = self._post_vlm(base_url, api_key, model, messages)
        if not desc:
            raise RuntimeError("VLM 返回空描述")
        return {
            "name": name,
            "desc": desc,
            "sources": [label for _, label in images],
            "model": model,
            "source": "runtime",
            "ts": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        }

    def _ensure_index(self) -> Dict[str, Dict[str, Any]]:
        if self._index_cache is not None:
            return self._index_cache
        entries = load_index(
            self._data_dir,
            max_age_hours=self._index_refresh_hours,
            url=self._index_url,
        )
        self._index_cache = {str(item.get("emojiId")): item for item in entries if item.get("emojiId")}
        return self._index_cache

    def _vlm(self) -> tuple[str, str, str]:
        if self._vlm_cache is not None:
            return self._vlm_cache
        if self._vlm_error is not None:
            raise RuntimeError(self._vlm_error)
        try:
            self._vlm_cache = resolve_vlm_target(self._resolve_model_config())
        except Exception as error:  # noqa: BLE001 - 记下来避免反复读盘报错
            self._vlm_error = str(error)
            raise
        return self._vlm_cache

    def _resolve_model_config(self) -> Path:
        candidates = [self._model_config_path] if self._model_config_path else []
        env_path = os.environ.get("MAIBOT_MODEL_CONFIG", "").strip()
        if env_path:
            candidates.append(env_path)
        candidates.extend(MODEL_CONFIG_CANDIDATES)
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return Path(candidate)
        raise RuntimeError("找不到 MaiBot 的 model_config.toml，无法解析默认 VLM")

    def _post_vlm(self, base_url: str, api_key: str, model: str,
                  messages: list[Dict[str, Any]]) -> str:
        body = {
            "model": model,
            "temperature": 0.2,
            "max_tokens": 400,
            "messages": messages,
        }
        request = urllib.request.Request(
            f"{base_url.rstrip('/')}/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=self._timeout_s) as response:
            parsed = json.loads(response.read())
        content = parsed["choices"][0]["message"]["content"]
        return clean_description(content, self._desc_max_chars)


WORKER: Optional[FaceVisionWorker] = None


def request(face_id: str) -> None:
    """供消息链路调用的薄封装：没启动 worker 时静默忽略。"""
    worker = WORKER
    if worker is None:
        return
    try:
        worker.request(face_id)
    except Exception:  # noqa: BLE001 - 绝不因补描述出错而中断消息处理
        pass


async def start(worker: FaceVisionWorker) -> None:
    """注册并启动全局 worker。"""
    global WORKER
    WORKER = worker
    await worker.start()


async def stop() -> None:
    """停止并注销全局 worker。"""
    global WORKER
    worker, WORKER = WORKER, None
    if worker is not None:
        await worker.stop()

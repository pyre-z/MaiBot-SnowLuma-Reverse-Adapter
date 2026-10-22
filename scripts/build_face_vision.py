#!/usr/bin/env python3
"""离线生成 QQ 内置表情的视觉描述表。

为 ``qq_face_parse_mode = "vision"`` 提供 ``snowluma_reverse/data/face_vision.json``：
把每个 QQ 表情交给 VLM 看一遍，把「长什么样、什么动作、什么情绪」缓存成一句中文描述，
运行期只查表，零额外调用、零延迟。

素材来源（两级，按质量优先）：

1. QFace 仓库 PNG（128×128，395/537 有图）—— 干净、静态、最好读；
2. 腾讯 qzone CDN GIF（24×24，537/537 有 ``qzoneCode``）—— 抽 5 帧放大后横向拼条，
   动作信息比单帧更全，实测 VLM 读得很准。

用法::

    export PYRE_Z_API_KEY=sk-...            # 或 --api-key
    python3 scripts/build_face_vision.py --sample 30      # 抽样试跑
    python3 scripts/build_face_vision.py                  # 全量（幂等，只补新增/变更）

图片只落在 ``.cache/face_vision``（腾讯素材不提交）；仓库里只提交生成的描述 JSON。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# 素材获取、提示词与清洗逻辑与运行期共用同一份实现，避免两边漂移。
from snowluma_reverse.media.face_vision_assets import (  # noqa: E402
    DESC_MAX_CHARS,
    INDEX_URL,
    build_messages,
    clean_description,
    collect_images,
    load_index,
)

DEFAULT_MODEL = "gemini-3.8-flash"
DEFAULT_BASE_URL = "https://api.example.com/v1"


# --------------------------------------------------------------------------- #
# 素材获取
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# VLM
# --------------------------------------------------------------------------- #
def describe(api_key: str, base_url: str, model: str, name: str,
             images: list[tuple[bytes, str]], limit: int = DESC_MAX_CHARS,
             timeout: float = 120.0, retries: int = 3) -> str:
    body = {
        "model": model,
        "temperature": 0.2,
        "max_tokens": 400,
        "messages": build_messages(name, images, limit),
    }
    payload = json.dumps(body).encode()
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                f"{base_url.rstrip('/')}/chat/completions",
                data=payload,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                parsed = json.loads(resp.read())
            return clean_description(parsed["choices"][0]["message"]["content"], limit)
        except Exception as exc:  # noqa: BLE001 - 网络/上游都可能抛
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"VLM 调用失败: {last_error}")


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def select_entries(entries: list[dict[str, Any]], ids: list[str] | None, sample: int | None) -> list[dict[str, Any]]:
    if ids:
        wanted = {str(i).strip() for i in ids}
        return [e for e in entries if str(e["emojiId"]) in wanted]
    if sample and sample < len(entries):
        must = [e for e in entries if str(e["emojiId"]) in {"187", "203", "211", "185", "14"}]
        step = len(entries) / float(sample)
        picked = {id(e) for e in must}
        chosen = list(must)
        for i in range(sample - len(chosen)):
            candidate = entries[min(len(entries) - 1, int(i * step))]
            while id(candidate) in picked:
                candidate = entries[(entries.index(candidate) + 1) % len(entries)]
            picked.add(id(candidate))
            chosen.append(candidate)
        return chosen
    return entries


def load_existing(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("faces", {})
    except json.JSONDecodeError:
        return {}


def save_result(path: Path, faces: dict[str, Any], model: str) -> None:
    payload = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "model": model,
            "source_index": INDEX_URL,
            "count": len(faces),
        },
        "faces": dict(sorted(faces.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0)),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 QQ 表情的 VLM 描述缓存")
    parser.add_argument("--out", default="snowluma_reverse/data/face_vision.json")
    parser.add_argument("--cache-dir", default=".cache/face_vision")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default=os.environ.get("FACE_VISION_API_KEY") or os.environ.get("PYRE_Z_API_KEY", ""))
    parser.add_argument("--limit", type=int, default=0, help="只处理前 N 个（调试用）")
    parser.add_argument("--sample", type=int, default=0, help="均匀抽样 N 个（含 187/203/211/185/14）")
    parser.add_argument("--ids", default="", help="只处理这些 id，逗号分隔")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--refresh", action="store_true", help="忽略已有结果，全部重跑")
    parser.add_argument("--refresh-index", action="store_true", help="重新下载 QFace 索引")
    parser.add_argument("--skip-hidden", action="store_true", help="跳过 isHide 的表情")
    parser.add_argument("--dry-run", action="store_true", help="只取图不调模型")
    parser.add_argument("--desc-max-chars", type=int, default=DESC_MAX_CHARS, help="描述字符上限")
    parser.add_argument("--no-combine", action="store_true", help="只用动作帧，不做静态图+动作帧合并")
    args = parser.parse_args()
    # .env 里的 key 常带引号，复制粘贴过来会多两个字
    args.api_key = (args.api_key or "").strip().strip('"').strip("'")

    if not args.api_key and not args.dry_run:
        return int(bool(sys.stderr.write("缺少 API key：设置 PYRE_Z_API_KEY 或传 --api-key\n")))

    out_path = Path(args.out)
    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    entries = load_index(cache_dir, refresh=args.refresh_index, max_age_hours=10 ** 9)
    if args.skip_hidden:
        entries = [e for e in entries if not e.get("isHide")]
    if args.limit:
        entries = entries[: args.limit]
    entries = select_entries(entries, [x for x in args.ids.split(",") if x.strip()] or None, args.sample or None)

    faces = load_existing(out_path)
    todo: list[dict[str, Any]] = []
    for entry in entries:
        emoji_id = str(entry["emojiId"])
        if args.refresh or emoji_id not in faces:
            todo.append(entry)

    print(f"索引 {len(entries)} 条，待处理 {len(todo)} 条（已有 {len(faces)} 条）", flush=True)

    def work(entry: dict[str, Any]) -> tuple[str, dict[str, Any] | None, str]:
        emoji_id = str(entry["emojiId"])
        name = str(entry.get("describe") or "").lstrip("/").strip() or f"表情{emoji_id}"
        started = time.time()
        try:
            images = collect_images(entry, cache_dir, combine=not args.no_combine)
            if not images:
                return emoji_id, None, "no-image"
            sources = [label for _, label in images]
            if args.dry_run:
                return emoji_id, {"name": name, "desc": "", "sources": sources,
                                  "img_sha256": hashlib.sha256(b"".join(d for d, _ in images)).hexdigest()}, "dry-run"
            desc = describe(args.api_key, args.base_url, args.model, name, images, args.desc_max_chars)
            return emoji_id, {
                "name": name,
                "desc": desc,
                "sources": sources,
                "img_sha256": hashlib.sha256(b"".join(d for d, _ in images)).hexdigest(),
                "model": args.model,
                "ts": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
                "elapsed_s": round(time.time() - started, 1),
            }, "ok"
        except Exception as exc:  # noqa: BLE001
            return emoji_id, None, f"error: {exc}"

    failures: list[tuple[str, str]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        for done, (emoji_id, result, status) in enumerate(pool.map(work, todo), start=1):
            if result is None:
                failures.append((emoji_id, status))
                print(f"  [{done}/{len(todo)}] {emoji_id} ✗ {status}", flush=True)
                continue
            faces[emoji_id] = result
            print(f"  [{done}/{len(todo)}] {emoji_id} {result['name']} ← {'+'.join(result['sources'])}: {result['desc']}", flush=True)
            if done % 10 == 0 and not args.dry_run:
                save_result(out_path, faces, args.model)

    if not args.dry_run:
        save_result(out_path, faces, args.model)
    print(f"\n已写入 {out_path}：共 {len(faces)} 条，失败 {len(failures)} 条")
    for emoji_id, status in failures:
        print(f"  - {emoji_id}: {status}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

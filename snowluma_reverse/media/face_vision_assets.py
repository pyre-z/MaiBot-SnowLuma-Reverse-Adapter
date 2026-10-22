"""QQ 表情素材获取与 VLM 提示词（离线脚本与运行时共用）。

素材两级：

1. **QFace 仓库 PNG**（128×128，覆盖 395/537）—— 干净、静态，定形象；
2. **腾讯 qzone CDN GIF**（24×24，537/537 都有 ``qzoneCode``）—— 抽 5 帧放大拼条，定动作。

两路一起送 VLM 时描述最准（静态定形象、动作帧定动作），缺一路自动降级。
"""

from __future__ import annotations

import base64
import io
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from PIL import Image

INDEX_URL = "https://koishi.js.org/QFace/assets/qq_emoji/_index.json"
ASSET_BASE = "https://koishi.js.org/QFace/"
QZONE_GIF = "https://qzonestyle.gtimg.cn/qzone/em/e{qzone_code}.gif"
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://qzone.qq.com/",
}
DESC_MAX_CHARS = 45

SHARED_TAIL = (
    "请用一句不超过 {limit} 字的中文，说清它画的是什么形象（长相/颜色/道具）、"
    "正在做什么动作、传达什么情绪或常用于什么语境，"
    "供聊天模型判断对方发这个表情的意思。"
    "直接用描述，不要分点、不要引号、不要解释。"
)
PROMPT_COMBINED = (
    "这是 QQ 聊天软件的内置表情，中文名「{name}」。"
    "第一张是它的静态图，第二张是同一表情按时间顺序抽出的连续动作帧（从左到右）。" + SHARED_TAIL
)
PROMPT_FRAMES = (
    "这是 QQ 聊天软件的内置表情，中文名「{name}」。"
    "图为它的连续动作帧（从左到右）。" + SHARED_TAIL
)
PROMPT_STATIC = "这是 QQ 聊天软件的内置表情，中文名「{name}」。" + SHARED_TAIL

_RESAMPLE_NEAREST = getattr(Image, "Resampling", Image).NEAREST


def http_get(url: str, timeout: float = 30.0) -> bytes:
    """带 QQ 表情素材常用请求头取字节。"""
    request = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def load_index(cache_dir: Path, refresh: bool = False, max_age_hours: float = 24.0,
               url: str = INDEX_URL) -> List[Dict[str, Any]]:
    """读取 QFace 索引，过期或强制时重新下载；下载失败时退回本地缓存。"""
    cache = cache_dir / "qface_index.json"
    fresh = cache.exists() and (time.time() - cache.stat().st_mtime) < max_age_hours * 3600
    if cache.exists() and fresh and not refresh:
        return _parse_index(cache.read_bytes())
    try:
        raw = http_get(url, timeout=40)
    except Exception:
        if cache.exists():
            return _parse_index(cache.read_bytes())
        raise
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(raw)
    return _parse_index(raw)


def _parse_index(raw: bytes) -> List[Dict[str, Any]]:
    index = json.loads(raw)
    if not isinstance(index, list):
        raise RuntimeError("QFace 索引结构异常：期望 list")
    return index


def flatten(image: Image.Image, background: Tuple[int, int, int] = (255, 255, 255)) -> Image.Image:
    """合成到白底：素材带透明通道，直接送模型会发黑或糊成一团。"""
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        canvas = Image.new("RGBA", image.size, background + (255,))
        canvas.alpha_composite(image)
        return canvas.convert("RGB")
    return image.convert("RGB")


def upscale_to_min_side(image: Image.Image, min_side: int = 128) -> Image.Image:
    """小图放大到至少 ``min_side``，用 NEAREST 保住像素块。"""
    if min(image.size) >= min_side:
        return image
    factor = max(1, -(-min_side // min(image.size)))
    return image.resize((image.width * factor, image.height * factor), _RESAMPLE_NEAREST)


def png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def gif_storyboard(raw: bytes, frames: int = 5, scale: int = 6) -> bytes:
    """24×24 动图 → 采样 N 帧、放大后横向拼条，保留动作信息。"""
    image = Image.open(io.BytesIO(raw))
    total = int(getattr(image, "n_frames", 1))
    picks = [round(i * (total - 1) / (frames - 1)) for i in range(frames)] if total > 1 else [0]
    shots: List[Image.Image] = []
    for position in picks:
        image.seek(min(position, total - 1))
        min_side = image.height * scale if image.height < 96 else 128
        shots.append(upscale_to_min_side(flatten(image), min_side=min_side))
    width, height = shots[0].size
    gap = 4
    strip = Image.new("RGB", (width * len(shots) + gap * (len(shots) - 1), height), (230, 230, 230))
    for position, shot in enumerate(shots):
        strip.paste(shot, (position * (width + gap), 0))
    return png_bytes(strip)


def collect_images(entry: Dict[str, Any], cache_dir: Path, combine: bool = True) -> List[Tuple[bytes, str]]:
    """取该表情可用的图片，返回 ``[(png_bytes, label)]``；两路都拿不到时返回空列表。"""
    emoji_id = str(entry.get("emojiId") or "").strip() or "unknown"
    slot = cache_dir / "images"
    slot.mkdir(parents=True, exist_ok=True)
    images: List[Tuple[bytes, str]] = []

    static_path = slot / f"{emoji_id}-static.png"
    for asset in entry.get("assets") or []:
        path = str(asset.get("path") or "")
        if not (path.endswith(".png") and "/png/" in path):
            continue
        try:
            raw = http_get(urllib.parse.quote(ASSET_BASE + path, safe=":/"))
            data = png_bytes(upscale_to_min_side(flatten(Image.open(io.BytesIO(raw)))))
        except Exception:  # 静态图只是加分项，失败就只用动作帧
            continue
        static_path.write_bytes(data)
        images.append((data, "qface-png"))
        break

    frames_path = slot / f"{emoji_id}-frames.png"
    qzone_code = str(entry.get("qzoneCode") or "").strip()
    if qzone_code:
        try:
            data = gif_storyboard(http_get(QZONE_GIF.format(qzone_code=qzone_code)))
            frames_path.write_bytes(data)
            images.append((data, "qzone-gif"))
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
            if frames_path.exists():
                images.append((frames_path.read_bytes(), "qzone-gif"))

    return images[-1:] if (images and not combine) else images


def build_prompt(name: str, labels: Iterable[str], limit: int = DESC_MAX_CHARS) -> str:
    """按实际拿到的图源选择提示词：双图 / 仅动作帧 / 仅静态图。"""
    label_set = set(labels)
    if {"qface-png", "qzone-gif"} <= label_set:
        template = PROMPT_COMBINED
    elif "qzone-gif" in label_set:
        template = PROMPT_FRAMES
    else:
        template = PROMPT_STATIC
    return template.format(name=name, limit=limit)


def build_messages(name: str, images: Sequence[Tuple[bytes, str]],
                   limit: int = DESC_MAX_CHARS) -> List[Dict[str, Any]]:
    """组装 OpenAI 兼容的多图消息体。"""
    content: List[Dict[str, Any]] = [
        {"type": "text", "text": build_prompt(name, [label for _, label in images], limit)},
    ]
    for data, _label in images:
        content.append({
            "type": "image_url",
            "image_url": {"url": "data:image/png;base64," + base64.b64encode(data).decode()},
        })
    return [{"role": "user", "content": content}]


def clean_description(text: str, max_chars: int = DESC_MAX_CHARS) -> str:
    """压平空白、去掉“这是一张”之类开头，并按上限截断。"""
    cleaned = " ".join(str(text or "").split())
    for prefix in ("这是一张", "这张图片", "图片中", "图中"):
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].lstrip("是，, ：:的是")  # noqa: B005 - 按字符集剥离
    cleaned = cleaned.strip("“”\"'`。. ")  # noqa: B005 - 按字符集剥离
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rstrip("，,、；; ")
    return cleaned


def resolve_vlm_target(model_config_path: Path) -> Tuple[str, str, str]:
    """从 MaiBot 的 model_config.toml 解析默认 VLM 的 (base_url, api_key, model)。

    取 ``[model_task_config.vlm].model_list`` 里第一个走 OpenAI 兼容协议的模型，
    这样主人在 WebUI 换视觉模型时插件自动跟随，不需要另配一份密钥。

    Raises:
        RuntimeError: 配置文件不可读、或列表里没有 OpenAI 兼容的视觉模型。
    """
    import tomllib

    try:
        data = tomllib.loads(model_config_path.read_text(encoding="utf-8"))
    except OSError as error:
        raise RuntimeError(f"读取 MaiBot 模型配置失败: {error}") from error
    task = (data.get("model_task_config") or {}).get("vlm") or {}
    model_list = [str(item) for item in (task.get("model_list") or [])]
    models = {str(item.get("name")): item for item in (data.get("models") or [])}
    providers = {str(item.get("name")): item for item in (data.get("api_providers") or [])}
    for name in model_list:
        model = models.get(name)
        if not model:
            continue
        provider = providers.get(str(model.get("api_provider") or ""))
        if not provider or str(provider.get("client_type") or "openai") != "openai":
            continue
        base_url = str(provider.get("base_url") or "").strip().rstrip("/")
        api_key = str(provider.get("api_key") or "").strip()
        model_id = str(model.get("model_identifier") or name).strip()
        if base_url and api_key and model_id:
            return base_url, api_key, model_id
    raise RuntimeError(f"model_config 里没有可用的 OpenAI 兼容视觉模型: vlm.model_list={model_list}")

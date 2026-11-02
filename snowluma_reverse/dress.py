"""好友个性装扮（气泡 / 字体 / 主题 / 名片 …）查询。

数据源是 QQ 的 SSR 装扮页 ``zb.vip.qq.com/v2/pages/aioDressPage``：只要带登录态
cookie，按 ``targetUin`` 就能拿到对方正在用的全套装扮，其中 ``appId=2`` 就是聊天气泡，
``extraappinfo.extraInfo.immersiveMaterial`` 里带九宫格切图的全部 URL。

注意：SnowLuma 自己的 ``_get_friend_dress`` 会把 appId 2/5/23 过滤掉（源码注释认为
服务端不返回真值），实测是误判 —— 这里不复用它的过滤逻辑。
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import quote

import aiohttp

# 与 SnowLuma 的 protocol/src/web/friend-dress.ts 保持一致：装扮页只认移动端 QQ 的 UA。
DRESS_UA = (
    "Mozilla/5.0 (Linux; Android 13; 2109119BC Build/TKQ1.221114.001; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/121.0.6167.71 "
    "MQQBrowser/6.2 TBS/047925 Mobile Safari/537.36 V1_AND_SQ_9.2.66_13188_YYB_D "
    "QQ/9.2.66.33870 NetType/WIFI WebP/0.3.0 AppId/537339358"
)

# 装扮页要求的埋点串；开源仓库里被打码成这个字面量，服务端并不校验内容。
TRACE_DETAIL = "base64-eyJhcH...ZSI6%0AIiJ9%0A"

APP_KIND: Dict[int, str] = {
    2: "气泡",
    3: "主题",
    4: "挂件",
    5: "字体",
    8: "聊天背景",
    15: "名片",
    17: "来电",
    20: "个性装扮",
    22: "彩色屏保",
    23: "头像",
    47: "头像双击动作",
    305: "系统字体",
    352: "输入状态",
}

# 九宫格切图字段 → 中文方位，方便上层直接渲染或展示。
SLICE_FIELDS = {
    "staticTopLeft": "左上角",
    "staticTopRight": "右上角",
    "staticBottomLeft": "左下角",
    "staticBottomRight": "右下角",
    "staticTopMiddle": "上边",
    "staticBottomMiddle": "下边",
    "staticLeftMiddle": "左边",
    "staticRightMiddle": "右边",
    "staticAllMiddle": "中心",
    "staticAll": "整体预览",
    "animationAll": "动态整体预览",
}

_ASYNC_DATA_RE = re.compile(r"window\.__INITIAL_ASYNCDATA__\s*=\s*(\{[\s\S]*?\});\(function")


class DressError(Exception):
    """装扮查询失败，``kind`` 用于区分是网络、解析还是账号问题。"""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


def build_dress_url(uin: int) -> str:
    """拼出装扮页 URL（外层 aioDressPage 套内层 aioDressPage，与客户端请求一致）。"""
    inner = (
        "https://zb.vip.qq.com/v2/pages/aioDressPage"
        f"?fromPage=1&targetUin={uin}&widgetId=0&fontEffectId=0&bgId=custom"
        f"&chatId={uin}&isGroup=0&traceDetail={TRACE_DETAIL}"
    )
    query = (
        f"fromPage=1&enteranceId=aio&url={quote(inner, safe='')}"
        f"&fontEffectId=0&chatId={uin}&widgetId=0&targetUin={uin}&isGroup=0&bgId=custom"
        f"&traceDetail={TRACE_DETAIL}"
    )
    return f"https://zb.vip.qq.com/v2/pages/aioDressPage?{query}"


def parse_async_data(html: str) -> Dict[str, Any]:
    """从 SSR HTML 里抠出 ``window.__INITIAL_ASYNCDATA__``。"""
    match = _ASYNC_DATA_RE.search(html)
    if not match:
        raise DressError("parse", "装扮页里没有 __INITIAL_ASYNCDATA__（未登录态或页面改版）")
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise DressError("parse", f"__INITIAL_ASYNCDATA__ 不是合法 JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise DressError("parse", "__INITIAL_ASYNCDATA__ 顶层不是对象")
    return data


def extract_material(item: Mapping[str, Any]) -> Dict[str, str]:
    """取出九宫格切图 / 字体 / 主题素材的 URL 表。"""
    extra = item.get("extraappinfo")
    if not isinstance(extra, Mapping):
        return {}
    info = extra.get("extraInfo")
    if not isinstance(info, Mapping):
        return {}

    raw = info.get("immersiveMaterial")
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        material = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(material, dict):
        return {}

    return {
        label: value
        for key, label in SLICE_FIELDS.items()
        if isinstance(value := material.get(key), str) and value.startswith("http")
    }


def extract_text_color(item: Mapping[str, Any]) -> str:
    """气泡里的文字颜色（ARGB 字符串，如 ``0xFF2554c1``）。"""
    extra = item.get("extraappinfo")
    info = extra.get("extraInfo") if isinstance(extra, Mapping) else None
    raw = info.get("immersiveMaterial") if isinstance(info, Mapping) else None
    if not isinstance(raw, str) or not raw.strip():
        return ""
    try:
        material = json.loads(raw)
    except json.JSONDecodeError:
        return ""
    color = material.get("color") if isinstance(material, dict) else None
    return color if isinstance(color, str) else ""


def summarize(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """把装扮页原始数据整理成稳定结构。"""
    target_uin = str(payload.get("targetUin") or "")
    if not target_uin:
        raise DressError("structure", "装扮页缺少 targetUin")

    raw_items = payload.get("rawUsingList")
    if not isinstance(raw_items, list):
        raise DressError("structure", "装扮页缺少 rawUsingList")

    items: List[Dict[str, Any]] = []
    for raw in raw_items:
        if not isinstance(raw, Mapping):
            continue
        app_id = raw.get("appId")
        if not isinstance(app_id, int):
            continue
        items.append(
            {
                "app_id": app_id,
                "kind": APP_KIND.get(app_id, f"appId={app_id}"),
                "item_id": raw.get("itemId") if isinstance(raw.get("itemId"), int) else 0,
                "name": str(raw.get("name") or ""),
                "preview_url": str(raw.get("image") or ""),
                "material": extract_material(raw),
                "text_color": extract_text_color(raw),
            }
        )

    return {
        "target_uin": target_uin,
        "is_svip": bool(payload.get("isSvip")),
        "avatar_url": str(payload.get("avatarImage") or ""),
        "items": items,
    }


def pick(items: List[Dict[str, Any]], app_id: int) -> Optional[Dict[str, Any]]:
    """按 appId 取第一项。"""
    for item in items:
        if item.get("app_id") == app_id:
            return item
    return None


async def fetch_dress(
    cookies: str,
    uin: int,
    *,
    timeout: float = 10.0,
) -> Dict[str, Any]:
    """带 cookie 拉一次装扮页，返回 ``summarize`` 的结构。"""
    if not cookies:
        raise DressError("auth", "缺少 vip.qq.com 的登录态 cookie")

    headers = {
        "Cookie": cookies,
        "User-Agent": DRESS_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://zb.vip.qq.com/",
    }
    client_timeout = aiohttp.ClientTimeout(total=timeout)
    try:
        async with aiohttp.ClientSession(timeout=client_timeout) as session:
            async with session.get(build_dress_url(uin), headers=headers) as resp:
                html = await resp.text()
    except aiohttp.ClientError as exc:
        raise DressError("network", f"装扮页请求失败: {exc}") from exc
    except TimeoutError as exc:
        raise DressError("network", "装扮页请求超时") from exc

    if "ptlogin2" in html and "_ASYNCDATA_" not in html:
        raise DressError("auth", "登录态失效，装扮页被重定向到登录页")

    return summarize(parse_async_data(html))


def format_summary(data: Mapping[str, Any], nickname: str = "") -> str:
    """生成给模型看的中文摘要。"""
    uin = data.get("target_uin", "")
    who = f"{nickname}（{uin}）" if nickname else str(uin)
    lines = [f"{who} 正在使用的个性装扮："]

    for app_id in (2, 5, 3, 4, 15, 17, 22, 352, 8):
        item = pick(data.get("items") or [], app_id)
        if not item:
            continue
        name = item.get("name") or "未命名"
        lines.append(f"- {item['kind']}：{name}（itemId {item['item_id']}）")

    bubble = pick(data.get("items") or [], 2)
    if bubble:
        slices = bubble.get("material") or {}
        if slices:
            lines.append(f"- 气泡九宫格切片：{len(slices)} 张，可直接用于自绘气泡")
        if bubble.get("preview_url"):
            lines.append(f"- 气泡预览图：{bubble['preview_url']}")

    if len(lines) == 1:
        lines.append("- 没有查到可用的装扮")
    return "\n".join(lines)

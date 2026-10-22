"""Stable helpers shared by the typed configuration sections."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from maibot_sdk import Field

def _schema_i18n(
    *,
    label_en: str,
    label_ja: str,
    hint_en: Optional[str] = None,
    hint_ja: Optional[str] = None,
    placeholder_en: Optional[str] = None,
    placeholder_ja: Optional[str] = None,
) -> Dict[str, Dict[str, str]]:
    """构造 WebUI 配置项多语言说明，保留外层中文字段兼容旧格式。"""

    i18n: Dict[str, Dict[str, str]] = {
        "en_US": {"label": label_en},
        "ja_JP": {"label": label_ja},
    }
    if hint_en is not None:
        i18n["en_US"]["hint"] = hint_en
    if hint_ja is not None:
        i18n["ja_JP"]["hint"] = hint_ja
    if placeholder_en is not None:
        i18n["en_US"]["placeholder"] = placeholder_en
    if placeholder_ja is not None:
        i18n["ja_JP"]["placeholder"] = placeholder_ja
    return i18n


def _notice_field(
    *,
    label: str,
    description: str,
    order: int,
    label_en: str,
    label_ja: str,
) -> Any:
    """构造通知事件开关字段，统一默认放行与 WebUI 多语言标签。"""

    return Field(
        default=True,
        description=description,
        json_schema_extra={
            "hint": description,
            "i18n": _schema_i18n(label_en=label_en, label_ja=label_ja),
            "label": label,
            "order": order,
        },
    )



def _normalize_positive_float(value: Any, default: float) -> float:
    """规范化正浮点数配置值。

    Args:
        value: 原始配置值。
        default: 非法取值时使用的默认值。

    Returns:
        float: 合法的正浮点数；非法时回退到默认值。
    """

    if isinstance(value, (int, float)) and float(value) > 0:
        return float(value)

    if isinstance(value, str):
        try:
            parsed_value = float(value.strip())
        except ValueError:
            return default
        if parsed_value > 0:
            return parsed_value

    return default


def _normalize_positive_int(value: Any, default: int) -> int:
    """规范化正整数配置值。

    Args:
        value: 原始配置值。
        default: 非法取值时使用的默认值。

    Returns:
        int: 合法的正整数；非法时回退到默认值。
    """

    if isinstance(value, int) and value > 0:
        return value

    if isinstance(value, str):
        normalized_value = value.strip()
        if normalized_value.isdigit():
            parsed_value = int(normalized_value)
            if parsed_value > 0:
                return parsed_value

    return default


def _normalize_string(value: Any) -> str:
    """规范化字符串配置值。

    Args:
        value: 原始配置值。

    Returns:
        str: 去除首尾空白后的字符串；若值为空则返回空字符串。
    """

    return "" if value is None else str(value).strip()


def _normalize_string_list(value: Any) -> List[str]:
    """规范化字符串列表配置值。

    Args:
        value: 原始配置值。

    Returns:
        List[str]: 去除空白与重复项后的字符串列表。
    """

    if not isinstance(value, list):
        return []

    normalized_values: List[str] = []
    seen_values = set()
    for item in value:
        item_text = _normalize_string(item)
        if not item_text or item_text in seen_values:
            continue
        seen_values.add(item_text)
        normalized_values.append(item_text)
    return normalized_values

# Public version marker shared with consumers of config helpers.

from ..constants import SUPPORTED_CONFIG_VERSION  # noqa: E402, F401

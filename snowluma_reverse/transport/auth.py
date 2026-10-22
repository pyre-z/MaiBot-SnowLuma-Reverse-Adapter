"""反向连接鉴权规则。"""

from __future__ import annotations

import hmac
import ipaddress
from typing import Any


def token_matches(request: Any, token: str) -> bool:
    """验证 OneBot 标准 Bearer 或 access_token 令牌。"""
    if not token:
        return False
    authorization = str(request.headers.get("Authorization") or "").strip()
    provided = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
    if not provided:
        provided = str(request.query.get("access_token") or "").strip()
    return bool(provided) and hmac.compare_digest(provided, token)


def is_ip_allowed(remote: str | None, allowed_ips: list[str]) -> bool:
    """判断请求 IP 是否命中 IP/CIDR 白名单。"""
    if not allowed_ips:
        return True
    if not remote:
        return False
    try:
        address = ipaddress.ip_address(remote)
    except ValueError:
        return False
    for entry in allowed_ips:
        try:
            candidate = str(entry or "").strip()
            if "/" in candidate:
                if address in ipaddress.ip_network(candidate, strict=False):
                    return True
            elif address == ipaddress.ip_address(candidate):
                return True
        except ValueError:
            continue
    return False


def authorize_request(request: Any, config: Any) -> tuple[bool, str]:
    """验证来源 IP 与令牌。"""
    if not is_ip_allowed(request.remote, config.allowed_ips):
        return False, "来源 IP 不在白名单内"
    if not config.token:
        return True, ""
    if not token_matches(request, config.token):
        return False, "访问令牌缺失或不匹配"
    return True, ""


def authorize_self_id(self_id: str, config: Any) -> tuple[bool, str]:
    """验证握手中的机器人账号标识。"""
    expected = str(config.expect_self_id or "").strip()
    actual = str(self_id or "").strip()
    if expected and not actual:
        return False, "缺少 X-Self-ID"
    if expected and actual != expected:
        return False, f"X-Self-ID 不匹配（期望 {expected}，收到 {actual}）"
    return True, ""

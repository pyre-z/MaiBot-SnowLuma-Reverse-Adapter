"""QQ 群组与频道 API 端点（按能力拆成 mixin，组合回 ``QQGroupApiMixin``）。"""

from __future__ import annotations

from .ban import QQGroupBanMixin
from .info import QQGroupInfoMixin
from .manage import QQGroupManageMixin
from .member import QQGroupMemberMixin
from .notice import QQGroupNoticeMixin


class QQGroupApiMixin(
    QQGroupBanMixin,
    QQGroupInfoMixin,
    QQGroupManageMixin,
    QQGroupMemberMixin,
    QQGroupNoticeMixin,
):
    """QQ 群组、频道与群扩展相关 API。"""


__all__ = ["QQGroupApiMixin"]

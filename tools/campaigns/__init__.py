"""Every campaign the world knows, in id order.

Order is permanent: a new game appends, so no existing chapter, item or
location id moves.
"""

from __future__ import annotations

from .base import Campaign
from .hl2 import HL2

CAMPAIGNS: list[Campaign] = [HL2]
CAMPAIGNS_BY_KEY: dict[str, Campaign] = {c.key: c for c in CAMPAIGNS}

__all__ = ["Campaign", "CAMPAIGNS", "CAMPAIGNS_BY_KEY"]

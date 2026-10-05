"""Every campaign the world knows, in id order.

Order is permanent: a new game appends, so no existing chapter, item or
location id moves.
"""

from __future__ import annotations

from .base import Campaign
from .hl2 import HL2

CAMPAIGNS: list[Campaign] = [HL2]

# The hub: where a run starts, where a finished chapter returns to, and the one
# map no chapter owns. A stock background map until the project ships its own;
# it must be in a campaign's `excluded_maps` and hold nothing that fires a
# check. The dll reads it from checkdata.txt (`B|<map>`), so this is the only
# place to change it.
HUB_MAP = "background05"
CAMPAIGNS_BY_KEY: dict[str, Campaign] = {c.key: c for c in CAMPAIGNS}

__all__ = ["Campaign", "CAMPAIGNS", "CAMPAIGNS_BY_KEY", "HUB_MAP"]

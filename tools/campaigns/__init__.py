"""Every campaign the world knows, in id order.

Order is permanent: a new game appends, so no existing chapter, item or
location id moves.
"""

from __future__ import annotations

from .base import Campaign
from .hl2 import HL2

CAMPAIGNS: list[Campaign] = [HL2]

# The hub: where a run starts, where a finished chapter returns to, and the one
# map no chapter owns. Until the project ships its own, it is a stock menu
# background copied in under this name at install (`HUB_SOURCE_MAP`, see
# `half_life_2.mod.HUB_MAP_SOURCE`): the engine will not save on a map named
# background*, and hub warp points are saves. It must hold nothing that fires a
# check. The dll reads it from checkdata.txt (`B|<map>`).
HUB_MAP = "temp_hub"
HUB_SOURCE_MAP = "background05"
CAMPAIGNS_BY_KEY: dict[str, Campaign] = {c.key: c for c in CAMPAIGNS}

__all__ = ["Campaign", "CAMPAIGNS", "CAMPAIGNS_BY_KEY", "HUB_MAP", "HUB_SOURCE_MAP"]

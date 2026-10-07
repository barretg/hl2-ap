"""Every campaign the world knows, in id order.

Order is permanent: a new game appends, so no existing chapter, item or
location id moves.
"""

from __future__ import annotations

from .base import Campaign
from .hl2 import HL2

CAMPAIGNS: list[Campaign] = [HL2]

# The hub: where a run starts, where a finished chapter returns to, and the one
# map no chapter owns. Our own map: `maps/<HUB_MAP>.vmf` in the repo, compiled to
# the `.bsp` beside it, which the apworld bundles and installs. The engine will
# not save on a map named background*, and hub warp points are saves. It must
# hold nothing that fires a check. The dll reads it from checkdata.txt
# (`B|<map>`).
HUB_MAP = "alpha_hub"
CAMPAIGNS_BY_KEY: dict[str, Campaign] = {c.key: c for c in CAMPAIGNS}

__all__ = ["Campaign", "CAMPAIGNS", "CAMPAIGNS_BY_KEY", "HUB_MAP"]

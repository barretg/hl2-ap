"""Phase 7 (features): its subgroups in turn."""

from __future__ import annotations

from scenario import Group


GROUP = Group("phase7", "Phase 7: Melee Throw and filler", lambda ctx: [],
              includes=("melee", "filler"))

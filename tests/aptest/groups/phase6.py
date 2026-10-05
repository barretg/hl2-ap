"""Phase 6 (HL2-specific logic): its subgroups in turn."""

from __future__ import annotations

from scenario import Group


GROUP = Group("phase6", "Phase 6: gravity gun stages, vehicles, logic gates",
              lambda ctx: [], includes=("gravity_gun", "vehicles", "logic"))

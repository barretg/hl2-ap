"""Phase 5 (core gameplay): its subgroups in turn."""

from __future__ import annotations

from scenario import Group


GROUP = Group("phase5", "Phase 5 core gameplay: gating, checks, travel, deaths",
              lambda ctx: [], includes=("gating", "checks", "travel", "deaths"))

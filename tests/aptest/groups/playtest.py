"""Everything a long play-test session should cover, in order: the phase
groups after the foundation. Verdicts are shared with each subgroup."""

from __future__ import annotations

from scenario import Group


GROUP = Group("playtest", "the whole game side, phase by phase", lambda ctx: [],
              includes=("phase5", "phase6", "phase7"))

"""The pickup sources the maps cannot prove: copies that are dropped, crated or
handed over rather than lying in the level. A subset of `sources`."""

from __future__ import annotations

from scenario import Group

from .sources import scenarios_for

GROUP = Group(
    "unproven",
    "pickup sources the maps cannot prove (drops, crates, gives)",
    lambda ctx: scenarios_for(ctx, lambda source: source.how != "placed"),
    needs_checkdata=True,
)

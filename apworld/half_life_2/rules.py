"""Access rules.

Gates come from the campaign data (`tools/campaigns/<game>.py`, baked into
`data/campaign.json`). A gate is `{"strict": [group, ...], "items": {item:
count}}`:

* **strict** groups are firepower: one item from each, under strict logic only.
* **items** are traversal (vehicle keys, gravity gun stages, the RPG where a
  gunship bars the way): each at its count, at every difficulty.

A gate sits on a chapter's entrance, on walking on into one of its later maps,
on the chapter's completion, or on one source of a "First ..." check. This
module only turns them into callables.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from BaseClasses import CollectionState

from .data import REQUIREMENT_GROUPS, campaign_of, mission_complete_event
from .options import LogicDifficulty

if TYPE_CHECKING:
    from . import HalfLife2World

Rule = Callable[[CollectionState], bool]


def group_items(world: "HalfLife2World", group: str) -> list[str]:
    """The items satisfying a requirement group that this seed can receive."""
    return [name for name in REQUIREMENT_GROUPS[group] if name in world.obtainable_item_names]


def gate_conditions(world: "HalfLife2World", gate: dict) -> list[Rule]:
    """One condition per requirement in a gate. A requirement naming nothing
    this seed can receive is not a gate."""
    player = world.player
    conditions: list[Rule] = []
    if world.options.logic_difficulty.value == LogicDifficulty.option_strict:
        for group in gate.get("strict", []):
            names = group_items(world, group)
            if names:
                conditions.append(lambda state, names=names: state.has_any(names, player))
    for name, count in gate.get("items", {}).items():
        if name in world.obtainable_item_names:
            conditions.append(
                lambda state, name=name, count=count: state.has(name, player, count)
            )
    return conditions


def all_of(conditions: list[Rule]) -> Rule | None:
    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]

    def rule(state: CollectionState) -> bool:
        return all(condition(state) for condition in conditions)

    return rule


def gate_rule(world: "HalfLife2World", gate: dict) -> Rule | None:
    return all_of(gate_conditions(world, gate))


def chapter_is_startable(world: "HalfLife2World", chapter: dict) -> bool:
    """Can this chapter be entered with nothing but its unlock and the
    starting items? The chapter open at the start must be one, or sphere one
    is empty and fill has nowhere to put the item that opens sphere two.
    Called before the pool exists, so it asks only whether a gate names
    anything this seed can receive beyond what the run starts with."""
    gate = chapter.get("gates", {})
    if world.options.logic_difficulty.value == LogicDifficulty.option_strict:
        for group in gate.get("strict", []):
            names = group_items(world, group)
            if names and not set(names) & set(world.starting_items):
                return False
    for name in gate.get("items", {}):
        if name in world.obtainable_item_names and name not in world.starting_items:
            return False
    return True


def chapter_entry_rule(world: "HalfLife2World", chapter: dict) -> Rule | None:
    """Rule for the Hub -> first map of a chapter."""
    player = world.player
    conditions = gate_conditions(world, chapter.get("gates", {}))
    if chapter["is_goal"]:
        # The seal: no item opens a finale, only its game's finished chapters.
        campaign = campaign_of(chapter)
        required = world.missions_required_by_campaign[campaign]
        event = mission_complete_event(campaign)
        conditions.append(lambda state: state.has(event, player, required))
    else:
        unlock = world.unlock_item_for_chapter[chapter["key"]]
        conditions.append(lambda state: state.has(unlock, player))
    return all_of(conditions)


def map_entry_rule(world: "HalfLife2World", chapter: dict, map_name: str) -> Rule | None:
    """Rule for walking on into one of a chapter's later maps."""
    return gate_rule(world, chapter.get("map_gates", {}).get(map_name, {}))


def complete_rule(world: "HalfLife2World", chapter: dict) -> Rule | None:
    """Rule on a chapter's completion check and the event it grants."""
    return gate_rule(world, chapter.get("complete_gates", {}))


def source_rule(world: "HalfLife2World", sources: list[dict]) -> Rule:
    """A "First ..." check: reachable through any one of its sources, each its
    map's region plus that source's own gate. Chapters are played in any
    order, so no single copy is the first a player meets. Location rules are
    re-evaluated every sweep, so reaching into map regions needs no indirect
    conditions."""
    player = world.player
    ways = [(source["map"], gate_rule(world, source.get("gates", {}))) for source in sources]

    def rule(state: CollectionState) -> bool:
        return any(
            state.can_reach_region(region, player) and (extra is None or extra(state))
            for region, extra in ways
        )

    return rule

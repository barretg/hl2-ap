from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Item, ItemClassification

from .data import EVENT_ITEM_NAMES, ITEMS

if TYPE_CHECKING:
    from . import HalfLife2World

GAME_NAME = "Half-Life 2"

CLASSIFICATIONS = {
    "progression": ItemClassification.progression,
    "useful": ItemClassification.useful,
    "filler": ItemClassification.filler,
    "trap": ItemClassification.trap,
}

item_table: dict[str, dict] = {entry["name"]: entry for entry in ITEMS}
item_name_to_id: dict[str, int] = {entry["name"]: entry["id"] for entry in ITEMS}

filler_items: list[str] = [e["name"] for e in ITEMS if e["classification"] == "filler"]
filler_weights: list[int] = [e.get("weight", 1) for e in ITEMS if e["classification"] == "filler"]

trap_items: list[str] = [e["name"] for e in ITEMS if e["classification"] == "trap"]
trap_weights: list[int] = [e.get("weight", 1) for e in ITEMS if e["classification"] == "trap"]

weapon_items: list[str] = [e["name"] for e in ITEMS if e.get("group") == "weapon"]
equipment_items: list[str] = [e["name"] for e in ITEMS if e.get("group") == "equipment"]
vehicle_key_items: list[str] = [e["name"] for e in ITEMS if e.get("group") == "vehicle_key"]

# Chapter key -> the item that unlocks it. Finales have none: they open once
# enough chapters are done.
unlock_item_for_chapter: dict[str, str] = {
    e["chapter"]: e["name"] for e in ITEMS if e.get("group") == "chapter"
}

item_name_groups: dict[str, set[str]] = {
    "Weapons": set(weapon_items),
    "Chapter Unlocks": set(unlock_item_for_chapter.values()),
    "Equipment": set(equipment_items),
    "Vehicle Keys": set(vehicle_key_items),
    "Vehicle Upgrades": {e["name"] for e in ITEMS if e.get("group") == "vehicle_upgrade"},
    "Abilities": {e["name"] for e in ITEMS if e.get("group") == "ability"},
    "Filler": set(filler_items),
    "Traps": set(trap_items),
}
item_name_groups = {k: v for k, v in item_name_groups.items() if v}


def copies(name: str) -> int:
    """How many of an item a seed places (Progressive Gravity Gun has four)."""
    return item_table[name].get("count", 1)


class HalfLife2Item(Item):
    game = GAME_NAME


def create_item(world: "HalfLife2World", name: str) -> HalfLife2Item:
    if name in EVENT_ITEM_NAMES:
        return HalfLife2Item(name, ItemClassification.progression, None, world.player)
    entry = item_table[name]
    return HalfLife2Item(name, CLASSIFICATIONS[entry["classification"]], entry["id"],
                         world.player)

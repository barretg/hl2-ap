from __future__ import annotations

from BaseClasses import Location

from .data import CHAPTERS, LOCATIONS

GAME_NAME = "Half-Life 2"

location_table: dict[str, dict] = {entry["name"]: entry for entry in LOCATIONS}
location_name_to_id: dict[str, int] = {entry["name"]: entry["id"] for entry in LOCATIONS}


def item_sources(entry: dict, excluded_chapters: set[str]) -> list[dict]:
    """The ways to a "First ..." check this seed counts: each source in an
    included chapter. Ally drops are never sources until an option exists."""
    return [
        source for source in entry.get("sources", ())
        if source["chapter"] not in excluded_chapters and source.get("how") != "ally"
    ]


def location_in_seed(entry: dict, excluded_chapters: set[str]) -> bool:
    """Whether a seed leaving these chapters out still contains this check. A
    "First ..." check is there while any source it counts is."""
    if "sources" in entry:
        return bool(item_sources(entry, excluded_chapters))
    return entry["chapter"] not in excluded_chapters


locations_by_map: dict[str, list[dict]] = {}
for _entry in LOCATIONS:
    locations_by_map.setdefault(_entry["map"], []).append(_entry)

location_name_groups: dict[str, set[str]] = {
    chapter["name"]: {e["name"] for e in LOCATIONS
                      if e["chapter"] == chapter["key"] and "sources" not in e}
    for chapter in CHAPTERS
}
location_name_groups["Chapter Completions"] = {
    e["name"] for e in LOCATIONS if e["trigger"]["type"] == "chapter_complete"
}
location_name_groups["Pickups"] = {e["name"] for e in LOCATIONS if "sources" in e}
location_name_groups["Chargers"] = {
    e["name"] for e in LOCATIONS if e["trigger"]["type"] == "charger"
}
# Archipelago rejects empty location name groups.
location_name_groups = {k: v for k, v in location_name_groups.items() if v}


class HalfLife2Location(Location):
    game = GAME_NAME

"""Region graph.

    Menu -> Hub -> (first map of each chapter) -> ... -> (last map of that chapter)

Each map is its own region, so a check in part 4 is gated behind parts 1 to
3 and a map gate cuts the chapter where it applies. Chapters are entered only
from the Hub, as in play: a chapter is warped into and returns to the hub
when done. Retail transitions inside a chapter are left alone.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Region

from .data import LOCATIONS, VICTORY, campaign_of, mission_complete_event
from .locations import HalfLife2Location, item_sources, locations_by_map
from .rules import chapter_entry_rule, complete_rule, gate_rule, map_entry_rule, source_rule

if TYPE_CHECKING:
    from . import HalfLife2World

MENU = "Menu"
HUB = "Hub"


def create_regions(world: "HalfLife2World") -> None:
    multiworld = world.multiworld
    player = world.player

    menu = Region(MENU, player, multiworld)
    hub = Region(HUB, player, multiworld)
    multiworld.regions += [menu, hub]
    menu.connect(hub)

    # An excluded chapter gets no regions, so its checks are not in the seed
    # at all rather than placed and unreachable.
    for chapter in world.included_chapters:
        previous: Region | None = None
        finish = complete_rule(world, chapter)
        for map_name in chapter["maps"]:
            region = Region(map_name, player, multiworld)
            multiworld.regions.append(region)
            for entry in locations_by_map.get(map_name, []):
                trigger = entry["trigger"]["type"]
                if trigger in world.excluded_triggers or "sources" in entry:
                    continue
                location = HalfLife2Location(player, entry["name"], entry["id"], region)
                if trigger == "chapter_complete" and finish is not None:
                    location.access_rule = finish
                elif "gates" in entry:
                    rule = gate_rule(world, entry["gates"])
                    if rule is not None:
                        location.access_rule = rule
                region.locations.append(location)
            if previous is None:
                hub.connect(region, f"Enter {chapter['name']}",
                            chapter_entry_rule(world, chapter))
            else:
                previous.connect(region, f"{chapter['name']}: {map_name}",
                                 map_entry_rule(world, chapter, map_name))
            previous = region
        assert previous is not None
        add_event(world, previous, chapter, finish)

    add_source_checks(world, hub)


def add_source_checks(world: "HalfLife2World", hub: Region) -> None:
    """Every "First ..." check, hung on the Hub. Its rule reaches into the
    map region of each source, so the check is in the seed while any source
    it counts is."""
    for entry in LOCATIONS:
        if "sources" not in entry or entry["trigger"]["type"] in world.excluded_triggers:
            continue
        sources = item_sources(entry, world.excluded_chapters)
        if not sources:
            continue
        location = HalfLife2Location(world.player, entry["name"], entry["id"], hub)
        location.access_rule = source_rule(world, sources)
        hub.locations.append(location)


def add_event(world: "HalfLife2World", region: Region, chapter: dict, finish) -> None:
    """Finishing a chapter grants an event: `Mission Complete`, which the
    finale's seal counts, or `Victory` for a finale."""
    name = VICTORY if chapter["is_goal"] else mission_complete_event(campaign_of(chapter))
    location = HalfLife2Location(world.player, f"{chapter['name']}: Chapter Cleared", None,
                                 region)
    if finish is not None:
        location.access_rule = finish
    location.place_locked_item(world.create_item(name))
    region.locations.append(location)

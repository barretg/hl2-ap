"""Build `campaign.json` and the id registry from the retail maps.

Everything the world, the client and the game read about chapters, maps and
locations comes from here, and everything here comes from the install:

- chapters from `cfg/chapterN.cfg` (each names its first map), titles from the
  game's localization file;
- each chapter's maps by walking the `trigger_changelevel` graph from its first
  map, stopping at the next chapter's;
- checks from the entity lumps: reaching each map, finishing each chapter,
  the first copy of each weapon, and every charger.

`ids.json` is append-only: a location or item keeps its id for good, a new one
gets the next free id, and nothing is ever renumbered.

Usage:
    python tools/build_campaign_data.py [--game <Half-Life 2 dir>] [--check]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))
sys.path.insert(0, str(REPO_ROOT / "apworld" / "half_life_2"))

from bsp_entities import (  # noqa: E402
    BspError, Entity, brush_model_bounds, load_map, world_position)
from campaigns import CAMPAIGNS, HUB_MAP, HUB_SOURCE_MAP, Campaign  # noqa: E402
from map_logic import MapLogic  # noqa: E402

DATA_DIR = REPO_ROOT / "apworld" / "half_life_2" / "data"
CAMPAIGN_PATH = DATA_DIR / "campaign.json"
IDS_PATH = DATA_DIR / "ids.json"

# 1: first format.
FORMAT_VERSION = 1

ITEM_ID_BASE = 8_820_000
LOCATION_ID_BASE = 8_830_000

# Preference among one map's copies, most provable first.
HOW_RANK = {"placed": 0, "crate": 1, "give": 2, "drop": 3}

# NPC spawnflag: never drop the weapon it carries.
SF_NPC_NO_WEAPON_DROP = 8192
# A charger this close to the transformed position of one across a seam is
# that one, rebuilt in the neighbouring map.
SEAM_TWIN_RADIUS = 32.0

# Items no map provides: abilities and filler. Traps join in Phase 7.
WORLD_ITEMS: list[tuple[str, str, str]] = [
    ("Melee Throw", "useful", "ability"),
    ("Ammo Cache", "filler", "filler"),
    ("Medkit", "filler", "filler"),
    ("Battery", "filler", "filler"),
]

# A weapon whose single item is several copies, each a stage.
PROGRESSIVE: dict[str, tuple[str, int]] = {
    "Gravity Gun": ("Progressive Gravity Gun", 4),
}

Vec3 = tuple[float, float, float]


class ScanError(RuntimeError):
    """The install and the campaign definition disagree; fix one of them."""


@dataclass
class MapData:
    name: str
    entities: list[Entity]
    logic: MapLogic
    bounds: dict[str, tuple[Vec3, Vec3]]

    def landmarks(self) -> dict[str, Vec3]:
        found: dict[str, Vec3] = {}
        for entity in self.entities:
            if entity.classname == "info_landmark" and entity.targetname and entity.origin:
                found[entity.targetname.lower()] = entity.origin
        return found


@dataclass
class Chapter:
    key: str
    number: str
    name: str
    maps: list[str] = field(default_factory=list)


def natural_key(number: str) -> tuple[int, str]:
    match = re.match(r"(\d+)(.*)", number)
    if not match:
        return (10**6, number)
    return (int(match.group(1)), match.group(2))


def title_case(raw: str) -> str:
    """`\"WE DON'T GO TO RAVENHOLM...\"` -> `We Don't Go to Ravenholm...`."""
    small = {"a", "an", "and", "of", "the", "to", "in", "on", "at", "for"}
    words = raw.replace('\\"', "").replace('"', "").strip().lower().split()
    out = []
    for i, word in enumerate(words):
        out.append(word if i and word in small else word[:1].upper() + word[1:])
    return " ".join(out)


def read_titles(path: Path) -> dict[str, str]:
    raw = path.read_bytes()
    text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8")
    titles: dict[str, str] = {}
    for match in re.finditer(r'^\s*"([^"]+)"\s+"((?:[^"\\]|\\.)*)"', text, re.M):
        titles[match.group(1).lower()] = match.group(2)
    return titles


def read_chapter_cfgs(cfg_dir: Path) -> list[tuple[str, str]]:
    """`(number, first map)` per `chapterN.cfg`, in chapter order."""
    found = []
    for path in cfg_dir.glob("chapter*.cfg"):
        number = path.stem[len("chapter"):]
        match = re.search(r"^\s*map\s+(\S+)", path.read_text(errors="replace"), re.M)
        if not match:
            raise ScanError(f"{path.name}: no `map` command")
        found.append((number, match.group(1)))
    return sorted(found, key=lambda pair: natural_key(pair[0]))


def load_maps(campaign: Campaign, maps_dir: Path) -> dict[str, MapData]:
    maps: dict[str, MapData] = {}
    for bsp in sorted(maps_dir.glob("*.bsp")):
        try:
            entities = load_map(bsp)
            bounds = brush_model_bounds(bsp)
        except BspError as exc:
            if bsp.stem in campaign.excluded_maps:
                continue
            raise ScanError(str(exc)) from exc
        maps[bsp.stem] = MapData(bsp.stem, entities, MapLogic(entities), bounds)
    return maps


def changelevel_edges(maps: dict[str, MapData]) -> dict[str, list[tuple[str, str, Entity]]]:
    """`{map: [(destination, landmark, trigger)]}`, in entity order.

    Self-loops are dropped: Valve puts touch-disabled changelevels to the same
    map at seams to stop the player walking back, and they lead nowhere.
    """
    edges: dict[str, list[tuple[str, str, Entity]]] = {}
    for name, data in maps.items():
        found = []
        for entity in data.entities:
            if entity.classname != "trigger_changelevel":
                continue
            destination = entity.get("map")
            if destination == name or destination not in maps:
                continue
            found.append((destination, entity.get("landmark").lower(), entity))
        edges[name] = found
    return edges


def assign_chapters(campaign: Campaign, cfgs: list[tuple[str, str]], titles: dict[str, str],
                    maps: dict[str, MapData],
                    edges: dict[str, list[tuple[str, str, Entity]]]) -> list[Chapter]:
    chapters: list[Chapter] = []
    for number, first in cfgs:
        if number in campaign.non_chapters:
            continue
        if first not in maps:
            raise ScanError(f"chapter{number}.cfg names {first!r}, which is not a map")
        title = titles.get(campaign.title_key.format(n=number).lower())
        if title is None:
            raise ScanError(f"no title {campaign.title_key.format(n=number)!r}")
        chapters.append(Chapter(first, number, title_case(title)))
    firsts = {c.key for c in chapters}
    assigned: dict[str, str] = {}
    for chapter in chapters:
        # Depth first, edges in entity order: a hub map revisited mid-chapter
        # (Ravenholm's d1_town_02) is listed where the player first meets it.
        stack = [chapter.key]
        while stack:
            current = stack.pop()
            if current in assigned:
                continue
            assigned[current] = chapter.key
            chapter.maps.append(current)
            for destination, _, _ in reversed(edges[current]):
                if destination not in assigned and destination not in firsts:
                    stack.append(destination)
    for name in maps:
        if name in assigned and name in campaign.excluded_maps:
            raise ScanError(f"{name} is excluded but reachable from {assigned[name]}")
        if name not in assigned and name not in campaign.excluded_maps:
            raise ScanError(f"{name} is in no chapter; add it to excluded_maps or fix the graph")
    if campaign.goal_chapter not in firsts:
        raise ScanError("goal chapter is not a chapter key")
    return chapters


def chapter_exits(chapters: list[Chapter], edges: dict[str, list[tuple[str, str, Entity]]],
                  goal: str) -> dict[str, list[tuple[str, str]]]:
    """`{chapter: [(from map, to map)]}`: the changelevels into the next chapter."""
    exits: dict[str, list[tuple[str, str]]] = {}
    for index, chapter in enumerate(chapters):
        if chapter.key == goal:
            continue
        if index + 1 >= len(chapters):
            raise ScanError(f"{chapter.key} is last but is not the goal")
        following = chapters[index + 1].key
        found = sorted({(m, d) for m in chapter.maps for d, _, _ in edges[m] if d == following})
        if not found:
            raise ScanError(f"{chapter.key} has no changelevel into {following}")
        exits[chapter.key] = found
    return exits


def rounded(position: Vec3) -> list[int]:
    return [int(round(v)) for v in position]


def beyond_trigger(at: Vec3, landmark: Vec3, mins: Vec3, maxs: Vec3) -> bool:
    """Is `at` on the far side of this changelevel slab from `landmark`?

    The slab's thinnest axis is the one crossed; the side is a sign along it.
    """
    extents = [maxs[i] - mins[i] for i in range(3)]
    axis = extents.index(min(extents))
    centre = (mins[axis] + maxs[axis]) / 2
    from_landmark = landmark[axis] - centre
    from_point = at[axis] - centre
    if from_landmark == 0 or from_point == 0:
        return False
    return (from_landmark > 0) != (from_point > 0)


def charger_units(campaign: Campaign, data: MapData) -> list[tuple[str, Vec3]]:
    found = []
    for index, entity in enumerate(data.entities):
        if entity.classname in campaign.chargers and data.logic.exists_in_play(index):
            if entity.origin is not None:
                found.append((entity.classname, entity.origin))
    return found


def seam_twins(campaign: Campaign, chapters: list[Chapter], maps: dict[str, MapData],
               edges: dict[str, list[tuple[str, str, Entity]]]) -> set[tuple[str, str, tuple[int, ...]]]:
    """`(map, classname, rounded position)` for chargers walled off behind a
    transition that also exist on the other side.

    Valve built each seam room into both maps, so a charger at the end of one
    is rebuilt at the start of the next, past the trigger that would take the
    player back. Only a provable duplicate is dropped: the copy on the far side
    of the trigger from its landmark, with a twin at the same spot relative to
    the same landmark in the other map. If both copies qualify, the earlier map
    in campaign order keeps its own.
    """
    order = {m: i for i, m in enumerate(m for c in chapters for m in c.maps)}
    sealed: set[tuple[str, str, tuple[int, ...]]] = set()
    pairs = []
    for name in order:
        data = maps[name]
        here = data.landmarks()
        for destination, landmark, trigger in edges[name]:
            model = trigger.get("model")
            if landmark not in here or destination not in order or model not in data.bounds:
                continue
            there = maps[destination].landmarks().get(landmark)
            if there is None:
                continue
            offset = trigger.origin or (0.0, 0.0, 0.0)
            mins, maxs = data.bounds[model]
            mins = tuple(mins[i] + offset[i] for i in range(3))
            maxs = tuple(maxs[i] + offset[i] for i in range(3))
            shift = [there[i] - here[landmark][i] for i in range(3)]
            for classname, at in charger_units(campaign, data):
                if not beyond_trigger(at, here[landmark], mins, maxs):  # type: ignore[arg-type]
                    continue
                twin = tuple(at[i] + shift[i] for i in range(3))
                for other_class, other_at in charger_units(campaign, maps[destination]):
                    if other_class == classname and math.dist(twin, other_at) <= SEAM_TWIN_RADIUS:
                        mine = (name, classname, tuple(rounded(at)))
                        theirs = (destination, classname, tuple(rounded(other_at)))
                        sealed.add(mine)
                        pairs.append((mine, theirs))
                        break
    for mine, theirs in pairs:
        if mine in sealed and theirs in sealed:
            sealed.discard(min(mine, theirs, key=lambda unit: order[unit[0]]))
    return sealed


def copy_excluded(spec: list[str], map_name: str, position: Vec3 | None) -> bool:
    for entry in spec:
        where, _, at = entry.partition("@")
        if where != map_name:
            continue
        if not at:
            return True
        if position is not None and math.dist(tuple(float(v) for v in at.split()), position) <= 16:
            return True
    return False


def item_sources(campaign: Campaign, chapters: list[Chapter], maps: dict[str, MapData],
                 classnames: list[str], item: str,
                 allowed: set[str] | None = None) -> list[dict]:
    """Every chapter's first way to a copy of this item, in campaign order,
    looking only at `allowed` maps when given.

    A copy is a placed or play-spawned entity, a supply crate holding it, an
    enemy that drops it (an ally only with `"drop": "ally"`), or a scripted
    `give`. Cold-load kits are never copies.
    """
    wanted = set(classnames)
    unreachable = campaign.unreachable_copies.get(item, [])
    confirmed = campaign.confirmed_copies.get(item, [])
    sources: list[dict] = []
    for chapter in chapters:
        best: dict | None = None
        ally: dict | None = None
        for map_name in chapter.maps:
            if allowed is not None and map_name not in allowed:
                continue
            data = maps[map_name]
            for index, entity in enumerate(data.entities):
                if not data.logic.exists_in_play(index):
                    continue
                classname = entity.classname
                position = entity.origin
                how = None
                if classname in wanted:
                    how = "placed"
                elif classname == "item_item_crate" and entity.get("ItemClass") in wanted:
                    how = "crate"
                elif entity.get("additionalequipment") in wanted:
                    npc = entity.get("NPCType") if classname.startswith("npc_maker") else classname
                    spawnflags = int(entity.get("spawnflags", "0") or 0)
                    if spawnflags & SF_NPC_NO_WEAPON_DROP:
                        continue
                    if npc in campaign.enemy_npcs:
                        how = "drop"
                    elif npc in campaign.ally_npcs:
                        how = "ally"
                elif classname == "point_clientcommand":
                    how = scripted_give(data, index, wanted)
                    position = None
                elif input_give(campaign, data, index, wanted):
                    how = "give"
                if how is None or copy_excluded(unreachable, map_name, position):
                    continue
                source = {"chapter": chapter.key, "map": map_name, "how": how}
                # Exclusions above match the map-file origin; the scenario
                # needs where the copy really appears.
                position = data.logic.made_at.get(index, position)
                if position is not None:
                    source["position"] = rounded(position)
                spawner = data.logic.spawner_of.get(index)
                if spawner and spawner[0]:
                    # Exists only once this fires: a scenario placing the
                    # player here skips whatever would have.
                    source["spawner"] = f"{spawner[0]},{spawner[1]}"
                if copy_excluded(confirmed, map_name, entity.origin):
                    source["confirmed"] = True
                if how == "ally":
                    ally = ally or source
                elif best is None or HOW_RANK[how] < HOW_RANK[best["how"]]:
                    # Within one map, the copy the maps prove best: a placed
                    # one beats a drop from an enemy who may never be met.
                    best = source
            if best:
                break
        if best:
            sources.append(best)
        elif ally:
            sources.append({**ally, "drop": "ally"})
    return sources


def scripted_give(data: MapData, index: int, wanted: set[str]) -> str | None:
    """`give` if some output tells this point_clientcommand to give a wanted item."""
    for parameter in data.logic.receives(index, "Command"):
        words = parameter.split()
        if len(words) == 2 and words[0] == "give" and words[1] in wanted:
            return "give"
    return None


def upgrade_point(order: list[str], maps: dict[str, MapData], classname: str,
                  output: str) -> tuple[str, Vec3] | None:
    """The first map (and the trigger's position) where a `classname` trigger
    in play fires `output`."""
    for map_name in order:
        data = maps[map_name]
        for index, entity in enumerate(data.entities):
            if entity.classname != classname or not data.logic.exists_in_play(index):
                continue
            if any(name.lower() == output.lower() for name, _ in entity.outputs()):
                position = world_position(entity, data.bounds)
                if position is not None:
                    return map_name, position
    return None


def input_give(campaign: Campaign, data: MapData, index: int, wanted: set[str]) -> bool:
    """Does some output send this entity an input whose code spawns a wanted item?"""
    return any(classname in wanted and data.logic.receives(index, name)
               for name, classname in campaign.input_gives.items())


def vehicles_by_chapter(campaign: Campaign, chapters: list[Chapter],
                        maps: dict[str, MapData]) -> dict[str, list[str]]:
    """`{chapter: [vehicle script]}` for chapters the player drives in.

    A drivable vehicle is known by its script (an APC can be a
    `prop_vehicle_jeep` with an NPC script). A chapter drives if one is in
    play on any of its maps, or in a cold-load kit on any map but its first:
    a kit there means the player is expected to arrive carrying it, while a
    kit on the first map alone is only how the last chapter's ride arrives
    (Black Mesa East's parked airboat).
    """
    found: dict[str, list[str]] = {}
    for chapter in chapters:
        scripts: list[str] = []
        for position, map_name in enumerate(chapter.maps):
            data = maps[map_name]
            for index, entity in enumerate(data.entities):
                script = entity.get("vehiclescript").lower()
                if script not in campaign.vehicles or script in scripts:
                    continue
                if data.logic.exists_in_play(index) or position > 0:
                    scripts.append(script)
        if scripts:
            found[chapter.key] = scripts
    return found


def airboat_gun_maps(order: list[str], maps: dict[str, MapData]) -> list[str]:
    """Maps where the level turns on the airboat's mounted gun."""
    return [m for m in order
            if maps[m].logic.inputs_to({"prop_vehicle_airboat"}, "EnableGun")]


def buggy_gun_maps(order: list[str], maps: dict[str, MapData]) -> list[str]:
    """Maps with the buggy, whose tau cannon is always mounted."""
    return [m for m in order
            if any(e.get("vehiclescript").lower() == "scripts/vehicles/jeep_test.txt"
                   for e in maps[m].entities)]


@dataclass
class Registry:
    items: dict[str, int]
    locations: dict[str, int]

    @staticmethod
    def load(path: Path) -> "Registry":
        if not path.exists():
            return Registry({}, {})
        raw = json.loads(path.read_text(encoding="utf-8"))
        return Registry(dict(raw["items"]), dict(raw["locations"]))

    def item(self, name: str) -> int:
        if name not in self.items:
            self.items[name] = max([ITEM_ID_BASE - 1, *self.items.values()]) + 1
        return self.items[name]

    def location(self, key: str) -> int:
        if key not in self.locations:
            self.locations[key] = max([LOCATION_ID_BASE - 1, *self.locations.values()]) + 1
        return self.locations[key]

    def dump(self) -> str:
        return json.dumps({"items": dict(sorted(self.items.items())),
                           "locations": dict(sorted(self.locations.items()))},
                          indent=1) + "\n"


def build_campaign(campaign: Campaign, game_root: Path, registry: Registry) -> dict:
    game_dir = game_root / campaign.game_dir
    maps = load_maps(campaign, game_dir / "maps")
    titles = read_titles(game_dir / campaign.resource_file)
    edges = changelevel_edges(maps)
    chapters = assign_chapters(campaign, read_chapter_cfgs(game_dir / "cfg"), titles, maps, edges)
    exits = chapter_exits(chapters, edges, campaign.goal_chapter)
    order = [m for c in chapters for m in c.maps]
    names = {c.key: campaign.display(c.name) for c in chapters}
    vehicles = vehicles_by_chapter(campaign, chapters, maps)

    locations: list[dict] = []

    def add(key: str, name: str, chapter: str, map_name: str, trigger: dict, **extra) -> None:
        locations.append({"id": registry.location(key), "key": key, "name": name,
                          "campaign": campaign.key, "chapter": chapter, "map": map_name,
                          "trigger": trigger, **extra})

    sealed = seam_twins(campaign, chapters, maps, edges)
    for chapter in chapters:
        for part, map_name in enumerate(chapter.maps, start=1):
            add(f"{campaign.key}|{chapter.key}|{map_name}|map_reached",
                f"{names[chapter.key]}: Part {part} Reached", chapter.key, map_name,
                {"type": "map_reached", "map": map_name})
        for part, map_name in enumerate(chapter.maps, start=1):
            counts: dict[str, int] = {}
            units = charger_units(campaign, maps[map_name])
            totals: dict[str, int] = {}
            kept = []
            for classname, at in units:
                unit = (map_name, classname, tuple(rounded(at)))
                hand = campaign.unreachable_chargers.get(map_name, set())
                if unit in sealed or (classname, tuple(rounded(at))) in hand:
                    continue
                kept.append((classname, at))
                totals[classname] = totals.get(classname, 0) + 1
            for classname, at in kept:
                counts[classname] = counts.get(classname, 0) + 1
                label = campaign.chargers[classname]
                if totals[classname] > 1:
                    label = f"{label} {counts[classname]}"
                at_key = " ".join(str(v) for v in rounded(at))
                add(f"{campaign.key}|{chapter.key}|{map_name}|charger|{classname}@{at_key}",
                    f"{names[chapter.key]}: {label} (Part {part})", chapter.key, map_name,
                    {"type": "charger", "map": map_name, "classname": classname, "at": at_key},
                    position=rounded(at))
        complete_on = "finale" if chapter.key == campaign.goal_chapter else "forward_exit"
        add(f"{campaign.key}|{chapter.key}||chapter_complete",
            f"{names[chapter.key]}: Complete", chapter.key, chapter.maps[-1],
            {"type": "chapter_complete", "chapter": chapter.key, "on": complete_on})

    # `{weapon item: maps whose copies are its upgraded form}`, and the
    # upgrade checks themselves, built after the weapons.
    upgraded: dict[str, set[str]] = {}
    confiscated: set[str] = set()
    upgrade_checks = []
    for name, (weapon, trigger_class, output) in campaign.upgrades.items():
        point = upgrade_point(order, maps, trigger_class, output)
        if point is None:
            raise ScanError(f"no {trigger_class} firing {output}: nothing gives {name}")
        later = set(order[order.index(point[0]) + 1:])
        upgraded[weapon] = later
        if name == campaign.confiscating_upgrade:
            confiscated = set(order[order.index(point[0]):])
        upgrade_checks.append((name, weapon, point, later))

    pickups = [(item, classnames, "weapon_pickup") for item, classnames in campaign.weapons.items()]
    # Equipment with no pickup (the flashlight) has no "First ..." check.
    pickups += [(item, classnames, "item_pickup")
                for item, classnames in campaign.equipment.items() if classnames]
    for item, classnames, kind in pickups:
        if item in upgraded:
            allowed = set(order) - upgraded[item]
        elif kind == "weapon_pickup":
            allowed = set(order) - confiscated
        else:
            allowed = None
        sources = item_sources(campaign, chapters, maps, classnames, item, allowed)
        direct = [s for s in sources if s.get("drop") != "ally"]
        if not direct:
            raise ScanError(f"no reachable copy of {item} anywhere in {campaign.name}")
        anchor = direct[0]
        add(f"{campaign.key}|*|{kind}|{classnames[0]}", campaign.display(f"First {item}"),
            anchor["chapter"], anchor["map"],
            {"type": kind, "map": anchor["map"], "classnames": classnames},
            sources=sources, **({"position": anchor["position"]} if "position" in anchor else {}))

    chapter_of = {m: c.key for c in chapters for m in c.maps}
    for name, weapon, (where, position), later in upgrade_checks:
        classnames = campaign.weapons[weapon]
        sources = [{"chapter": chapter_of[where], "map": where, "how": "upgrade",
                    "position": rounded(position)}]
        sources += item_sources(campaign, chapters, maps, classnames, name, later)
        add(f"{campaign.key}|*|weapon_upgrade|{classnames[0]}", campaign.display(f"First {name}"),
            chapter_of[where], where,
            {"type": "weapon_upgrade", "map": where, "classnames": classnames},
            sources=sources, position=rounded(position))

    items: list[dict] = []

    def add_item(name: str, classification: str, group: str, **extra) -> None:
        items.append({"id": registry.item(name), "name": name, "classification": classification,
                      "group": group, "campaign": campaign.key, **extra})

    for chapter in chapters:
        if chapter.key != campaign.goal_chapter:
            add_item(f"{names[chapter.key]} Unlock", "progression", "chapter", chapter=chapter.key)
    for item, classnames in campaign.weapons.items():
        if item in PROGRESSIVE:
            name, count = PROGRESSIVE[item]
            add_item(campaign.display(name), "progression", "weapon", classnames=classnames,
                     count=count)
        else:
            add_item(campaign.display(item), "progression", "weapon", classnames=classnames)
    for item, classnames in campaign.equipment.items():
        # As HL1: the suit gates armour and aux power, the flashlight only light.
        classification = campaign.equipment_classification.get(item, "progression")
        add_item(campaign.display(item), classification, "equipment", classnames=classnames)
    for chapter in chapters:
        for script in vehicles.get(chapter.key, []):
            add_item(campaign.vehicle_key_name.format(chapter=names[chapter.key],
                                                      vehicle=campaign.vehicles[script]),
                     "progression", "vehicle_key", chapter=chapter.key, vehiclescript=script)
    gun_maps = airboat_gun_maps(order, maps)
    if gun_maps:
        add_item(campaign.display("Airboat Gun"), "progression", "vehicle_upgrade",
                 maps=gun_maps)
    gun_maps = buggy_gun_maps(order, maps)
    if gun_maps:
        add_item(campaign.display("Buggy Gun"), "progression", "vehicle_upgrade",
                 maps=gun_maps)

    chapter_entries = [
        {"key": c.key, "number": c.number, "name": names[c.key], "maps": c.maps,
         "campaign": campaign.key, "is_goal": c.key == campaign.goal_chapter,
         "exits": [list(e) for e in exits.get(c.key, [])],
         "vehicles": vehicles.get(c.key, []),
         "kits": {m: kit_names(maps[m]) for m in c.maps if kit_names(maps[m])}}
        for c in chapters
    ]
    apply_logic(campaign, chapter_entries, items, locations)
    return {
        "campaign": {
            "key": campaign.key, "name": campaign.name, "short": campaign.short,
            "goal_chapter": campaign.goal_chapter,
            "starting_items": [campaign.display(n) for n in campaign.starting_items],
        },
        "chapters": chapter_entries,
        "requirement_groups": {
            k: [[campaign.display(n) for n in o] if isinstance(o, list) else campaign.display(o)
                for o in v]
            for k, v in campaign.requirement_groups.items()},
        "items": items,
        "locations": locations,
    }


def check_gate(campaign: Campaign, gate: dict, item_names: set[str], where: str) -> dict:
    """A gate record, checked against the campaign's items and groups."""
    unknown = set(gate) - {"strict", "any", "items"}
    if unknown:
        raise ScanError(f"{where}: unknown gate keys {sorted(unknown)}")
    for group in gate.get("strict", []) + gate.get("any", []):
        if group not in campaign.requirement_groups:
            raise ScanError(f"{where}: no requirement group {group!r}")
    for name, count in gate.get("items", {}).items():
        if campaign.display(name) not in item_names or count < 1:
            raise ScanError(f"{where}: no item {name!r} (or a bad count)")
    return {k: v for k, v in (
        ("strict", list(gate.get("strict", []))),
        ("any", list(gate.get("any", []))),
        ("items", {campaign.display(n): c for n, c in gate.get("items", {}).items()}),
    ) if v}


def apply_logic(campaign: Campaign, chapters: list[dict], items: list[dict],
                locations: list[dict]) -> None:
    """Write the campaign's gates into its chapters and checks, failing on
    any chapter, map, item or group name the data does not have."""
    item_names = {i["name"] for i in items}
    for group, options in campaign.requirement_groups.items():
        for option in options:
            if isinstance(option, list) and len(option) < 2:
                raise ScanError(f"requirement group {group!r}: a combination needs two items")
            for name in option if isinstance(option, list) else [option]:
                if campaign.display(name) not in item_names:
                    raise ScanError(f"requirement group {group!r}: no item {name!r}")
    for name in campaign.starting_items:
        if campaign.display(name) not in item_names:
            raise ScanError(f"starting item {name!r} is not an item")
    by_key = {c["key"]: c for c in chapters}
    for key, record in campaign.gates.items():
        chapter = by_key.get(key)
        if chapter is None:
            raise ScanError(f"gates for unknown chapter {key!r}")
        unknown = set(record) - {"entry", "maps", "complete"}
        if unknown:
            raise ScanError(f"{key}: unknown gate sections {sorted(unknown)}")
        if "entry" in record:
            chapter["gates"] = check_gate(campaign, record["entry"], item_names, key)
        if "complete" in record:
            chapter["complete_gates"] = check_gate(campaign, record["complete"], item_names,
                                                   f"{key} complete")
        map_gates = {}
        for map_name, gate in record.get("maps", {}).items():
            if map_name not in chapter["maps"][1:]:
                raise ScanError(f"{key}: {map_name} is not a later map of the chapter")
            map_gates[map_name] = check_gate(campaign, gate, item_names, f"{key} {map_name}")
        if map_gates:
            chapter["map_gates"] = map_gates
    checks = {l["name"]: l for l in locations if "sources" in l}
    for name, gate in campaign.source_gates.items():
        entry = checks.get(campaign.display(f"First {name}"))
        if entry is None:
            raise ScanError(f"source gates for unknown check First {name}")
        checked = check_gate(campaign, gate, item_names, f"First {name}")
        for source in entry["sources"]:
            source["gates"] = checked
    plain = {l["name"]: l for l in locations if "sources" not in l}
    for name, gate in campaign.check_gates.items():
        entry = plain.get(campaign.display(name))
        if entry is None:
            raise ScanError(f"check gates for unknown check {name}")
        entry["gates"] = check_gate(campaign, gate, item_names, name)


def kit_names(data: MapData) -> list[str]:
    """Targetnames of the pickups a map spawns only on a cold load (see
    `MapLogic`), shared by nothing that exists in play: the game must not
    count them as pickups."""
    kit, real = set(), set()
    for index, entity in enumerate(data.entities):
        name = (entity.targetname or "").lower()
        if not name or not entity.classname.startswith(("weapon_", "item_")):
            continue
        (real if data.logic.exists_in_play(index) else kit).add(name)
    return sorted(kit - real)


def data_version(items: list[dict], locations: list[dict]) -> str:
    """Changes exactly when an id the world publishes changes."""
    digest = hashlib.sha256()
    for entry in sorted([(i["name"], i["id"]) for i in items]
                        + [(l["key"], l["id"]) for l in locations]):
        digest.update(f"{entry[0]}={entry[1]}\n".encode())
    return digest.hexdigest()[:12]


def build(game_root: Path, registry: Registry) -> dict:
    campaigns, chapters, items, locations = [], [], [], []
    groups: dict[str, list[str]] = {}
    for campaign in CAMPAIGNS:
        built = build_campaign(campaign, game_root, registry)
        campaigns.append(built["campaign"])
        groups.update(built["requirement_groups"])
        chapters += built["chapters"]
        items += built["items"]
        locations += built["locations"]
    for name, classification, group in WORLD_ITEMS:
        items.append({"id": registry.item(name), "name": name,
                      "classification": classification, "group": group})
    if not any(HUB_SOURCE_MAP in c.excluded_maps for c in CAMPAIGNS):
        raise ScanError(f"hub source map {HUB_SOURCE_MAP} is in no campaign's excluded_maps")
    if not (game_root / CAMPAIGNS[0].game_dir / "maps" / f"{HUB_SOURCE_MAP}.bsp").is_file():
        raise ScanError(f"hub source map {HUB_SOURCE_MAP} is not in the install")
    return {"format": FORMAT_VERSION, "data_version": data_version(items, locations),
            "hub_map": HUB_MAP, "campaigns": campaigns, "chapters": chapters,
            "requirement_groups": groups, "items": items, "locations": locations}


def default_game_root() -> Path | None:
    import mod  # the apworld's mod package: Steam library lookup
    return mod.hl2_install_dir()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--game", type=Path, help="the Half-Life 2 install folder")
    parser.add_argument("--check", action="store_true",
                        help="fail if the committed data differs from a fresh build")
    args = parser.parse_args(argv)

    game_root = args.game or default_game_root()
    if game_root is None or not (game_root / "hl2" / "maps").is_dir():
        print("Half-Life 2 install not found; pass --game", file=sys.stderr)
        return 2
    registry = Registry.load(IDS_PATH)
    try:
        data = build(game_root, registry)
    except ScanError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    campaign_text = json.dumps(data, indent=1) + "\n"
    ids_text = registry.dump()
    if args.check:
        stale = [p.name for p, text in ((CAMPAIGN_PATH, campaign_text), (IDS_PATH, ids_text))
                 if not p.exists() or p.read_text(encoding="utf-8") != text]
        if stale:
            print(f"out of date: {', '.join(stale)}; run tools/build_campaign_data.py",
                  file=sys.stderr)
            return 1
        print("campaign data is current")
        return 0
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CAMPAIGN_PATH.write_text(campaign_text, encoding="utf-8")
    IDS_PATH.write_text(ids_text, encoding="utf-8")
    print(f"wrote {CAMPAIGN_PATH.relative_to(REPO_ROOT)}: {len(data['chapters'])} chapters, "
          f"{len(data['items'])} items, {len(data['locations'])} locations "
          f"(data version {data['data_version']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

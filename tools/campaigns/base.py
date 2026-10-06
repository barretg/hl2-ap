"""The shape of one campaign: everything about a game that is not shared.

A campaign is one retail game (Half-Life 2, later each episode) with its own
maps directory, chapters and finale. Adding one is a module that builds a
`Campaign` and a line in the registry in `__init__`; nothing here names a game.

What a campaign module states is only what the maps cannot: which chapter is
the finale, which maps are deliberately outside every chapter, and the
editorial calls confirmed in play. Chapter lists, map order and titles are read
from the install by `build_campaign_data.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Campaign:
    # Permanent: the first field of every location key in `data/ids.json`.
    key: str
    name: str
    # What a player types to name this campaign (`ap warp hl2 3`).
    short: str
    # The game directory under the install root whose `maps/`, `cfg/` and
    # `resource/` are read.
    game_dir: str
    # Localization file and the key pattern of a chapter title, `{n}` being the
    # chapter cfg's suffix (`9a` for `chapter9a.cfg`).
    resource_file: str
    title_key: str
    # Chapter numbers (cfg suffixes) that are not playable chapters, such as
    # Half-Life 2's `chapter14.cfg`, which loads the credits.
    non_chapters: frozenset[str]
    # The finale, by chapter key (its first map). Never unlocked by an item.
    goal_chapter: str
    # Maps in `maps/` deliberately in no chapter, so the scan fails on any map
    # nobody decided about.
    excluded_maps: frozenset[str]
    # Weapon items, `{item: [classname, ...]}`.
    weapons: dict[str, list[str]]
    # Upgraded forms of a weapon that are their own check, `{name: (weapon
    # item, trigger classname, output)}`: the first map where that trigger
    # fires that output upgrades a held weapon, and every later map's copies
    # are the upgraded form (Half-Life 2's Citadel supercharges the gravity
    # gun). The weapon's own check then counts only copies before it.
    upgrades: dict[str, tuple[str, str, str]] = field(default_factory=dict)
    # An upgrade (by name) whose trigger also confiscates every other weapon:
    # from its map on, no other weapon has a source (Half-Life 2's Citadel
    # dissolves dropped weapons too).
    confiscating_upgrade: str = ""
    # Equipment items, `{item: [classname, ...]}`.
    equipment: dict[str, list[str]] = field(default_factory=dict)
    # Classification of an equipment item when not "progression".
    equipment_classification: dict[str, str] = field(default_factory=dict)
    # NPC classes whose `additionalequipment` the player can take off their
    # body. Allies are listed separately: a weapon only an ally drops is a
    # source only behind an option.
    enemy_npcs: frozenset[str] = frozenset()
    ally_npcs: frozenset[str] = frozenset()
    # Drivable vehicles by `vehiclescript` (lowercase), and the key item name
    # pattern (`{chapter}` is the chapter's display name, `{vehicle}` the
    # vehicle's word from here).
    vehicles: dict[str, str] = field(default_factory=dict)
    vehicle_key_name: str = "{chapter} {vehicle} Keys"
    # Inputs whose game code spawns an item no entity names: `{input: classname}`
    # (a vortigaunt sent `ExtractBugbait` creates `weapon_bugbait`). The source
    # is placed at the entity receiving the input.
    input_gives: dict[str, str] = field(default_factory=dict)
    # Display names of charger classnames. Point entities in Source.
    chargers: dict[str, str] = field(default_factory=dict)
    # `{item: [map or map@x y z]}` copies of a weapon that do not count as a
    # source (out of reach, scripted). Same form as HL1's.
    unreachable_copies: dict[str, list[str]] = field(default_factory=dict)
    # `{item: [map or map@x y z]}` copies confirmed reachable in play that the
    # harness could not stage (a scripted sequence it skips). Logic is
    # unchanged; the `unproven` group stops asking about them.
    confirmed_copies: dict[str, list[str]] = field(default_factory=dict)
    # `{map: {(classname, (x, y, z))}}` chargers no player can reach that the
    # automatic seam-twin pass does not catch.
    unreachable_chargers: dict[str, set[tuple[str, tuple[int, int, int]]]] = field(
        default_factory=dict
    )
    # Logic. A gate is `{"strict": [requirement group, ...], "items": {item:
    # count}}`: every strict group needs one of its items (strict logic only),
    # every item its count (any difficulty). Item and group names are the
    # display names the world uses. Validated by the data build.
    #
    # `{group: [item, ...]}`, "any one of these".
    requirement_groups: dict[str, list[str]] = field(default_factory=dict)
    # `{chapter key: {"entry": gate, "maps": {map: gate}, "complete": gate}}`.
    # "entry" applies to the whole chapter, a "maps" gate to walking on into
    # that map (and so everything after it), "complete" to the chapter's
    # completion check and the mission it counts as.
    gates: dict[str, dict] = field(default_factory=dict)
    # `{check item name: gate}` on every source of that "First ..." check.
    source_gates: dict[str, dict] = field(default_factory=dict)
    # Items every run opens with; never in the pool.
    starting_items: list[str] = field(default_factory=list)
    # Prefix on this campaign's location and item names. Empty for the base
    # game; later games use their name so two games never share a name.
    name_prefix: str = ""

    def display(self, name: str) -> str:
        return f"{self.name_prefix}{name}"

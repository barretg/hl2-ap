"""Archipelago world for Half-Life 2.

The campaign is cut into its own chapters. Each stays locked until its unlock
item arrives, and weapons must be received before they can be picked up. The
run opens with one chapter playable and is won by finishing Dark Energy, which
no item unlocks: it opens once `missions_required` other chapters are done.

Chapters are entered from a hub, so a warp loads the first map fresh and the
loadout is reapplied on spawn. Transitions inside a chapter are the game's own.
The structure is per game, so the episodes can join later as more campaigns.
"""

from __future__ import annotations

from typing import Any, ClassVar

from BaseClasses import Tutorial
from Options import OptionGroup
from worlds.AutoWorld import WebWorld, World
from worlds.LauncherComponents import Component, Type, components, launch_subprocess

from .data import (
    ABILITY_ITEM_NAMES,
    CAMPAIGNS,
    CAMPAIGNS_BY_KEY,
    CHAPTERS,
    CHARGER_TRIGGER,
    HALF_LIFE_2,
    ITEMS,
    OPTIONAL_ITEM_NAMES,
    VICTORY,
    campaign_of,
)
from .items import (
    HalfLife2Item,
    copies,
    create_item,
    filler_items,
    filler_weights,
    item_name_groups,
    item_name_to_id,
    trap_items,
    trap_weights,
    unlock_item_for_chapter,
    weapon_items,
)
from .locations import location_name_groups, location_name_to_id
from .options import (
    ButterfingersReissue,
    HalfLife2Options,
    ShuffleFlashlight,
    ShuffleHevSuit,
    TrapPercentage,
)
from .regions import create_regions
from .rules import chapter_is_startable

GAME_NAME = "Half-Life 2"


def launch_client(*args: str) -> None:
    from .client.launcher import launch

    launch_subprocess(launch, name="HalfLife2Client", args=args)


components.append(
    Component(
        "Half-Life 2 Client",
        func=launch_client,
        component_type=Type.CLIENT,
        game_name=GAME_NAME,
        supports_uri=True,
    )
)


class HalfLife2Web(WebWorld):
    theme = "dirt"
    tutorials = [
        Tutorial(
            "Multiworld Setup Guide",
            "A guide to setting up Half-Life 2 for Archipelago.",
            "English",
            "setup_en.md",
            "setup/en",
            ["hl2-ap"],
        )
    ]
    option_groups = [
        OptionGroup("Equipment", [ShuffleHevSuit, ShuffleFlashlight]),
        OptionGroup("Traps", [TrapPercentage, ButterfingersReissue]),
    ]


class HalfLife2World(World):
    """Half-Life 2, with every chapter and every weapon locked behind
    Archipelago items."""

    game = GAME_NAME
    options_dataclass = HalfLife2Options
    options: HalfLife2Options
    web = HalfLife2Web()

    item_name_to_id = item_name_to_id
    location_name_to_id = location_name_to_id
    item_name_groups = item_name_groups
    location_name_groups = location_name_groups

    unlock_item_for_chapter: ClassVar[dict[str, str]] = unlock_item_for_chapter

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Options are assigned after construction; everything read from them
        # is filled in `generate_early`.
        # Items placed in this seed's pool.
        self.pool_item_names: set[str] = set()
        # Items the run opens with: the campaigns' starting items, plus
        # equipment left unshuffled.
        self.starting_items: list[str] = []
        self.starting_chapter: str = ""
        self.excluded_chapters: set[str] = set()
        self.excluded_triggers: set[str] = set()
        self.campaigns: list[str] = []
        self.missions_required_by_campaign: dict[str, int] = {}

    @property
    def obtainable_item_names(self) -> set[str]:
        """Every item this seed can ever hold. Gates naming anything else are
        not gates."""
        return self.pool_item_names | set(self.starting_items)

    @property
    def tracker_passthrough(self) -> dict[str, Any] | None:
        """The real seed's slot data when Universal Tracker re-generates: the
        starting chapter is rolled, so a local roll would disagree."""
        return getattr(self.multiworld, "re_gen_passthrough", {}).get(self.game)

    def interpret_slot_data(self, slot_data: dict[str, Any]) -> dict[str, Any]:
        """Universal Tracker's hook; returning the slot data asks it to
        generate again with it."""
        return slot_data

    @property
    def included_chapters(self) -> list[dict[str, Any]]:
        """Every chapter this seed contains, finales included."""
        return [c for c in CHAPTERS if c["key"] not in self.excluded_chapters]

    def generate_early(self) -> None:
        passthrough = self.tracker_passthrough

        self.campaigns = [HALF_LIFE_2]
        if passthrough:
            self.campaigns = list(passthrough.get("campaigns", self.campaigns))

        self.excluded_chapters = {c["key"] for c in CHAPTERS if campaign_of(c) not in self.campaigns}
        if not self.options.chargesanity:
            self.excluded_triggers.add(CHARGER_TRIGGER)
        if passthrough:
            # The tracker may run without the YAML; the seed's sets are truth.
            self.excluded_chapters = set(passthrough.get("excluded_chapters", ())) | {
                c["key"] for c in CHAPTERS if campaign_of(c) not in self.campaigns
            }
            self.excluded_triggers = set(passthrough.get("excluded_triggers", ()))

        included = {c["key"] for c in self.included_chapters}
        included_maps = {m for c in self.included_chapters for m in c["maps"]}
        items_by_name = {entry["name"]: entry for entry in ITEMS}

        for key in self.campaigns:
            for name in CAMPAIGNS_BY_KEY[key].get("starting_items", ()):
                if name not in self.starting_items:
                    self.starting_items.append(name)

        pool = {name for name in weapon_items
                if campaign_of(items_by_name[name]) in self.campaigns}
        for name, option in OPTIONAL_ITEM_NAMES.items():
            if getattr(self.options, option):
                pool.add(name)
            else:
                self.starting_items.append(name)
        pool.update(name for name, option in ABILITY_ITEM_NAMES.items()
                    if getattr(self.options, option))
        for entry in ITEMS:
            group = entry.get("group")
            if group == "chapter" and entry["chapter"] in included:
                pool.add(entry["name"])
            elif group == "vehicle_key" and entry["chapter"] in included:
                pool.add(entry["name"])
            elif group == "vehicle_upgrade" and set(entry.get("maps", ())) & included_maps:
                pool.add(entry["name"])
        self.pool_item_names = pool - set(self.starting_items)

        # Each finale's seal, clamped to the chapters this seed contains.
        wanted = {HALF_LIFE_2: self.options.missions_required.value}
        for key in self.campaigns:
            available = len([c for c in self.included_chapters
                             if not c["is_goal"] and campaign_of(c) == key])
            self.missions_required_by_campaign[key] = min(wanted.get(key, available), available)
        if passthrough:
            self.missions_required_by_campaign.update(
                passthrough.get("missions_required_by_campaign", {})
            )

        # The chapter open from the start has to be enterable with what the
        # run opens with, or sphere one is empty.
        chapters = [c for c in self.included_chapters if c["key"] in unlock_item_for_chapter]
        starting = None
        if passthrough:
            given = set(passthrough.get("starting_chapters", ()))
            starting = next((c for c in chapters if c["key"] in given), None)
        if starting is None:
            candidates = [c for c in chapters if chapter_is_startable(self, c)]
            starting = self.random.choice(candidates or chapters)
        self.starting_chapter = starting["key"]

        for name in self.starting_items:
            self.multiworld.push_precollected(self.create_item(name))
        self.multiworld.push_precollected(
            self.create_item(unlock_item_for_chapter[self.starting_chapter])
        )

    def create_regions(self) -> None:
        create_regions(self)

    def create_item(self, name: str) -> HalfLife2Item:
        return create_item(self, name)

    def create_items(self) -> None:
        starting_unlock = unlock_item_for_chapter[self.starting_chapter]
        pool: list[HalfLife2Item] = []
        for name in sorted(self.pool_item_names):
            if name == starting_unlock:
                continue
            pool += [self.create_item(name) for _ in range(copies(name))]
        remaining = len(self.multiworld.get_unfilled_locations(self.player)) - len(pool)
        if remaining < 0:
            raise AssertionError(f"{self.game}: {-remaining} more items than locations")
        pool += [self.create_item(name) for name in self.get_filler_names(remaining)]
        self.multiworld.itempool += pool

    def get_filler_names(self, count: int) -> list[str]:
        """Fill the leftover locations, with `trap_percentage` of them traps."""
        traps = round(count * self.options.trap_percentage.value / 100)
        names = self.random.choices(trap_items, weights=trap_weights, k=traps)
        names += self.random.choices(filler_items, weights=filler_weights, k=count - traps)
        # Otherwise every trap lands in the same stretch of the pool.
        self.random.shuffle(names)
        return names

    def get_filler_item_name(self) -> str:
        return self.random.choices(filler_items, weights=filler_weights, k=1)[0]

    def set_rules(self) -> None:
        # Entrance and location rules are attached in `create_regions`.
        player = self.player
        finales = len(self.campaigns)
        self.multiworld.completion_condition[player] = (
            lambda state: state.has(VICTORY, player, finales)
        )

    def fill_slot_data(self) -> dict[str, Any]:
        """What the client needs to drive the game, and what Universal Tracker
        needs to rebuild the seed without the YAML."""
        return {
            "campaigns": list(self.campaigns),
            "goal_chapters": {key: CAMPAIGNS_BY_KEY[key]["goal_chapter"]
                              for key in self.campaigns},
            "missions_required_by_campaign": dict(self.missions_required_by_campaign),
            "starting_chapters": [self.starting_chapter],
            "excluded_chapters": sorted(self.excluded_chapters),
            "excluded_triggers": sorted(self.excluded_triggers),
            "starting_items": list(self.starting_items),
            "logic_difficulty": self.options.logic_difficulty.current_key,
            "shuffle_hev_suit": bool(self.options.shuffle_hev_suit),
            "shuffle_flashlight": bool(self.options.shuffle_flashlight),
            "melee_throw": bool(self.options.melee_throw),
            "butterfingers_reissue": bool(self.options.butterfingers_reissue),
            "death_link": bool(self.options.death_link),
            "death_link_amnesty": self.options.death_link_amnesty.value,
        }

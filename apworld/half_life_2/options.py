from __future__ import annotations

from dataclasses import dataclass

from Options import (
    Choice,
    DeathLink,
    DefaultOnToggle,
    PerGameCommonOptions,
    Range,
    StartInventoryPool,
    Toggle,
)

from .data import HALF_LIFE_2, MAX_MISSIONS_BY_CAMPAIGN


class MissionsRequired(Range):
    """How many chapters open Dark Energy.

    Dark Energy is never unlocked by an item: it opens once this many other
    chapters have been finished. The default is every one of them.
    """

    display_name = "Chapters Required"
    range_start = 1
    range_end = MAX_MISSIONS_BY_CAMPAIGN[HALF_LIFE_2]
    default = range_end


class LogicDifficulty(Choice):
    """How much firepower logic assumes you need to clear a chapter.

    strict: a chapter is only expected of you once you own weapons suited to
    it: a firearm from Route Kanal, and an SMG, Pulse Rifle or Shotgun from
    Highway 17 on. The default.
    loose: firepower requirements are dropped. What a chapter cannot be
    crossed without still applies at any difficulty: its vehicle keys, the
    gravity gun stages, the RPG where a gunship or strider bars the way, and
    the Airboat Gun.
    """

    display_name = "Logic Difficulty"
    option_strict = 0
    option_loose = 1
    default = 0


class ExcludeIntroMissions(DefaultOnToggle):
    """Leave Point Insertion out of the seed: the train station and the walk
    through City 17, with nothing to fight. Turned on it goes entirely (no
    regions, no checks, no unlock item) and stops counting toward the
    chapters required."""

    display_name = "Exclude Point Insertion"


class Chargesanity(DefaultOnToggle):
    """Every health charger and suit charger is a check, sent the moment you
    use one (an empty charger counts). Off, the seed is the map, chapter and
    pickup checks only."""

    display_name = "Chargesanity"


class ShuffleHevSuit(Toggle):
    """Shuffle the HEV suit into the item pool.

    Until it arrives you have no armour and no aux power. The HUD and weapon
    selection work regardless. When off, you have it from the start.
    """

    display_name = "Shuffle HEV Suit"


class ShuffleFlashlight(Toggle):
    """Shuffle the flashlight into the item pool.

    Until the Flashlight arrives, the flashlight key does nothing. When off,
    you have it from the start, as in retail.
    """

    display_name = "Shuffle Flashlight"


class MeleeThrow(Toggle):
    """Add Melee Throw to the item pool.

    Once it arrives, secondary fire throws the crowbar. Walk over it to pick
    it back up. When off, there is no throw at all.
    """

    display_name = "Add Melee Throw"


class DeathLinkAmnesty(Range):
    """How many deaths are forgiven before one is sent to the multiworld.

    Only outgoing DeathLinks are affected: an incoming one always kills you.
    Each forgiven death says how much amnesty is left; once it runs out the
    next death goes out and the allowance starts again. Failing an objective
    (an escort lost, a fade to black) counts as a death. 0 sends every death.
    """

    display_name = "DeathLink Amnesty"
    range_start = 0
    range_end = 20
    default = 4


@dataclass
class HalfLife2Options(PerGameCommonOptions):
    missions_required: MissionsRequired
    logic_difficulty: LogicDifficulty
    exclude_intro_missions: ExcludeIntroMissions
    chargesanity: Chargesanity
    shuffle_hev_suit: ShuffleHevSuit
    shuffle_flashlight: ShuffleFlashlight
    melee_throw: MeleeThrow
    start_inventory_from_pool: StartInventoryPool
    death_link: DeathLink
    death_link_amnesty: DeathLinkAmnesty

"""Loader for the generated campaign data.

`campaign.json` is produced by `tools/build_campaign_data.py` from the retail
maps. The world, the client and the game's `checkdata.txt` all read it, so a
location id is defined in exactly one place.
"""

from __future__ import annotations

import json
import pkgutil
from typing import Any

DATA_FILE = "campaign.json"


def load_campaign() -> dict[str, Any]:
    """`pkgutil.get_data`, not a file read: inside a zipped `.apworld`,
    `__file__` points into the archive and `open()` fails."""
    raw = pkgutil.get_data(__name__, DATA_FILE)
    if raw is None:
        raise FileNotFoundError(f"{__name__}/{DATA_FILE} is missing from the world package")
    return json.loads(raw.decode("utf-8"))


CAMPAIGN: dict[str, Any] = load_campaign()

DATA_VERSION: str = CAMPAIGN["data_version"]
CAMPAIGNS: list[dict[str, Any]] = CAMPAIGN["campaigns"]
CHAPTERS: list[dict[str, Any]] = CAMPAIGN["chapters"]
ITEMS: list[dict[str, Any]] = CAMPAIGN["items"]
LOCATIONS: list[dict[str, Any]] = CAMPAIGN["locations"]

CAMPAIGNS_BY_KEY: dict[str, dict[str, Any]] = {c["key"]: c for c in CAMPAIGNS}
CHAPTERS_BY_KEY: dict[str, dict[str, Any]] = {c["key"]: c for c in CHAPTERS}
REQUIREMENT_GROUPS: dict[str, list[str | list[str]]] = CAMPAIGN["requirement_groups"]

# The base game. Later games (Phase 9) append to CAMPAIGNS.
HALF_LIFE_2 = "hl2"


def campaign_of(entry: dict[str, Any]) -> str:
    """The game a chapter or item belongs to; world-wide items have none."""
    return entry.get("campaign", HALF_LIFE_2)


# Chapters an item can open: everything but the finales.
UNLOCKABLE_CHAPTERS: list[dict[str, Any]] = [c for c in CHAPTERS if not c["is_goal"]]

# The ceiling of each game's `missions_required`.
MAX_MISSIONS_BY_CAMPAIGN: dict[str, int] = {
    c["key"]: len([ch for ch in UNLOCKABLE_CHAPTERS if campaign_of(ch) == c["key"]])
    for c in CAMPAIGNS
}

# Optional items and the toggle that shuffles them. Off, the item is granted
# at the start instead (an unshuffled suit must still turn armour on).
OPTIONAL_ITEM_NAMES: dict[str, str] = {
    "HEV Suit": "shuffle_hev_suit",
    "Flashlight": "shuffle_flashlight",
}

# Abilities that exist only when their toggle is on.
ABILITY_ITEM_NAMES: dict[str, str] = {"Melee Throw": "melee_throw"}

# Each copy lets the aux meter fill another quarter (game/src/ap_game.cpp).
AUX_POWER = "Progressive Aux Power"

# Trigger type of the charger checks, switched off by `chargesanity`.
CHARGER_TRIGGER = "charger"

# Event items carry no id and never reach the datapackage.
MISSION_COMPLETE = "Mission Complete"
VICTORY = "Victory"


def mission_complete_event(campaign: str) -> str:
    """What finishing one of this game's chapters grants. Each finale counts
    only its own game's chapters."""
    if campaign == HALF_LIFE_2:
        return MISSION_COMPLETE
    return f"{CAMPAIGNS_BY_KEY[campaign]['name']}: {MISSION_COMPLETE}"


EVENT_ITEM_NAMES: frozenset[str] = frozenset(
    [VICTORY, *(mission_complete_event(c["key"]) for c in CAMPAIGNS)]
)

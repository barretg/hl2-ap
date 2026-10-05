"""Names the dll acts on literally must exist in the data, or a rename in
the campaign silently ungates a feature in game."""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CAMPAIGN = json.loads((REPO / "apworld/half_life_2/data/campaign.json").read_text())
SRC = REPO / "game" / "src"

ITEM_CONSTANTS = {"kSuitItem", "kFlashlightItem", "kAirboatGunItem", "kGravityGunItem",
                  "kMeleeThrowItem"}


def constants() -> dict[str, str]:
    found = {}
    for path in SRC.glob("*.cpp"):
        for name, value in re.findall(r'const char\* const (k\w+) = "([^"]*)";', path.read_text()):
            found[name] = value
    return found


def test_item_constants_are_items() -> None:
    items = {i["name"] for i in CAMPAIGN["items"]}
    found = constants()
    assert ITEM_CONSTANTS <= set(found)
    for name in ITEM_CONSTANTS:
        assert found[name] in items, name


def test_vehicle_scripts_known() -> None:
    text = (SRC / "ap_game.cpp").read_text()
    scripts = set(re.findall(r'\{"(scripts/vehicles/[^"]+)", "prop_vehicle_\w+"\}', text))
    keys = {i["vehiclescript"] for i in CAMPAIGN["items"] if i["group"] == "vehicle_key"}
    assert keys <= scripts


def test_physcannon_is_the_progressive_item() -> None:
    found = constants()
    gun = next(i for i in CAMPAIGN["items"] if i["name"] == found["kGravityGunItem"])
    assert gun["classnames"] == [found["kPhyscannon"]]
    assert gun["count"] == 4

"""Id stability: every published id comes from the append-only registry."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))
sys.path.insert(0, str(REPO_ROOT / "apworld" / "half_life_2"))

import build_campaign_data as build  # noqa: E402
from data import CAMPAIGN, ITEMS, LOCATIONS  # noqa: E402

REGISTRY = json.loads(build.IDS_PATH.read_text(encoding="utf-8"))


def test_every_location_id_from_registry() -> None:
    for location in LOCATIONS:
        assert REGISTRY["locations"][location["key"]] == location["id"]


def test_every_item_id_from_registry() -> None:
    for item in ITEMS:
        assert REGISTRY["items"][item["name"]] == item["id"]


def test_registry_ids_unique_and_in_range() -> None:
    items, locations = REGISTRY["items"].values(), REGISTRY["locations"].values()
    assert len(set(items)) == len(items)
    assert len(set(locations)) == len(locations)
    assert all(build.ITEM_ID_BASE <= i < build.LOCATION_ID_BASE for i in items)
    assert all(i >= build.LOCATION_ID_BASE for i in locations)


def test_data_version_matches_ids() -> None:
    assert CAMPAIGN["data_version"] == build.data_version(ITEMS, LOCATIONS)


def test_registry_never_renumbers() -> None:
    registry = build.Registry({"a": 8_820_005}, {"x": 8_830_002})
    assert registry.item("a") == 8_820_005
    assert registry.item("b") == 8_820_006
    assert registry.location("y") == 8_830_003
    assert registry.location("x") == 8_830_002


def test_new_registry_starts_at_bases() -> None:
    registry = build.Registry({}, {})
    assert registry.item("a") == build.ITEM_ID_BASE
    assert registry.location("x") == build.LOCATION_ID_BASE

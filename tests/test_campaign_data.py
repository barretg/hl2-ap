"""The committed campaign data: consistent, matched by the game's data file, and
(when the install is present) identical to a fresh scan of the maps."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))
sys.path.insert(0, str(REPO_ROOT / "apworld" / "half_life_2"))

import build_campaign_data  # noqa: E402
import gen_checkdata  # noqa: E402
from data import CAMPAIGN, CHAPTERS, ITEMS, LOCATIONS  # noqa: E402


def test_every_map_in_one_chapter() -> None:
    maps = [m for c in CHAPTERS for m in c["maps"]]
    assert len(maps) == len(set(maps))
    for chapter in CHAPTERS:
        assert chapter["maps"][0] == chapter["key"]


def test_one_goal_per_campaign_and_it_is_last() -> None:
    for campaign in CAMPAIGN["campaigns"]:
        chapters = [c for c in CHAPTERS if c["campaign"] == campaign["key"]]
        goals = [c["key"] for c in chapters if c["is_goal"]]
        assert goals == [campaign["goal_chapter"]] == [chapters[-1]["key"]]


def test_forward_exit_from_every_chapter_but_the_finale() -> None:
    for index, chapter in enumerate(CHAPTERS):
        if chapter["is_goal"]:
            assert chapter["exits"] == []
            continue
        following = CHAPTERS[index + 1]["key"]
        assert chapter["exits"]
        for source, destination in chapter["exits"]:
            assert source in chapter["maps"] and destination == following


def test_every_map_reached_and_chapter_complete() -> None:
    reached = {l["map"] for l in LOCATIONS if l["trigger"]["type"] == "map_reached"}
    assert reached == {m for c in CHAPTERS for m in c["maps"]}
    complete = {l["chapter"] for l in LOCATIONS if l["trigger"]["type"] == "chapter_complete"}
    assert complete == {c["key"] for c in CHAPTERS}


def test_names_unique() -> None:
    names = [l["name"] for l in LOCATIONS]
    assert len(names) == len(set(names))
    items = [i["name"] for i in ITEMS]
    assert len(items) == len(set(items))


def test_pickup_checks_anchored_at_a_direct_source() -> None:
    for location in LOCATIONS:
        if location["trigger"]["type"] not in ("weapon_pickup", "item_pickup", "weapon_upgrade"):
            continue
        direct = [s for s in location["sources"] if s.get("drop") != "ally"]
        assert direct and direct[0]["map"] == location["map"]


def test_vehicle_keys_name_vehicle_chapters() -> None:
    keys = {i["chapter"] for i in ITEMS if i["group"] == "vehicle_key"}
    assert keys == {c["key"] for c in CHAPTERS if c["vehicles"]}


def test_checkdata_is_current() -> None:
    text = gen_checkdata.render(CAMPAIGN)
    assert gen_checkdata.OUT_PATH.read_text(encoding="utf-8") == text


def test_checkdata_records_parse() -> None:
    lines = [l for l in gen_checkdata.OUT_PATH.read_text(encoding="utf-8").splitlines()
             if l and not l.startswith("#")]
    widths = {"V": 2, "D": 2, "B": 2, "N": 5, "C": 10, "K": 3, "P": 4, "H": 4, "U": 3, "F": 7, "X": 3}
    for line in lines:
        fields = line.split("|")
        if fields[0] == "L":
            assert len(fields) in (6, 7), line
        else:
            assert len(fields) == widths[fields[0]], line
    location_ids = {int(l.split("|")[1]) for l in lines if l.startswith("L|")}
    assert location_ids == {l["id"] for l in LOCATIONS}


def test_matches_a_fresh_scan() -> None:
    root = build_campaign_data.default_game_root()
    if root is None:
        pytest.skip("Half-Life 2 install not found")
    registry = build_campaign_data.Registry.load(build_campaign_data.IDS_PATH)
    before = dict(registry.locations), dict(registry.items)
    fresh = build_campaign_data.build(root, registry)
    assert (registry.locations, registry.items) == before, "scan needs new ids; rebuild"
    assert fresh == CAMPAIGN, "campaign.json is stale; run tools/build_campaign_data.py"


def test_upgraded_copies_belong_to_the_upgrade_check() -> None:
    by_name = {l["name"]: l for l in LOCATIONS}
    super_gun, gun = by_name["First Super Gravity Gun"], by_name["First Gravity Gun"]
    assert super_gun["sources"][0]["how"] == "upgrade"
    upgrade_map = super_gun["sources"][0]["map"]
    order = [m for c in CHAPTERS for m in c["maps"]]
    after = set(order[order.index(upgrade_map) + 1:])
    assert all(s["map"] in after for s in super_gun["sources"][1:])
    assert not any(s["map"] in after for s in gun["sources"])

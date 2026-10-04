"""Logic gates baked into campaign.json name only real chapters, maps, items
and groups (the data build checks this; this guards the committed file)."""

from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "apworld/half_life_2/data/campaign.json"


def gates_of(campaign: dict):
    for chapter in campaign["chapters"]:
        for key in ("gates", "complete_gates"):
            if key in chapter:
                yield chapter, chapter[key]
        for map_name, gate in chapter.get("map_gates", {}).items():
            assert map_name in chapter["maps"][1:]
            yield chapter, gate
    for entry in campaign["locations"]:
        for source in entry.get("sources", ()):
            if "gates" in source:
                yield entry, source["gates"]


def test_gates_name_real_things() -> None:
    campaign = json.loads(DATA.read_text())
    items = {i["name"] for i in campaign["items"]}
    groups = campaign["requirement_groups"]
    assert all(set(members) <= items for members in groups.values())
    seen = 0
    for _, gate in gates_of(campaign):
        assert set(gate) <= {"strict", "items"}
        assert set(gate.get("strict", [])) <= set(groups)
        assert all(name in items and count >= 1 for name, count in gate.get("items", {}).items())
        seen += 1
    assert seen


def test_every_vehicle_key_gates_its_chapter() -> None:
    campaign = json.loads(DATA.read_text())
    chapters = {c["key"]: c for c in campaign["chapters"]}
    for item in campaign["items"]:
        if item["group"] != "vehicle_key":
            continue
        chapter = chapters[item["chapter"]]
        named = [g for key in ("gates", "complete_gates") for g in [chapter.get(key, {})]]
        named += list(chapter.get("map_gates", {}).values())
        assert any(item["name"] in g.get("items", {}) for g in named), item["name"]


def test_starting_items_are_items() -> None:
    campaign = json.loads(DATA.read_text())
    items = {i["name"] for i in campaign["items"]}
    for game in campaign["campaigns"]:
        assert set(game["starting_items"]) <= items

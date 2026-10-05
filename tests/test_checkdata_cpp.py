"""The game's checkdata parser against the generated file and campaign.json,
built natively like the bridge probe. A record the dll misreads shows up here
rather than as a check that never fires in game."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CHECKDATA = REPO / "apworld/half_life_2/mod/files/archipelago/checkdata.txt"
CAMPAIGN = json.loads((REPO / "apworld/half_life_2/data/campaign.json").read_text())
SOURCES = [REPO / "game" / "src" / name for name in ("ap_text.cpp", "ap_checkdata.cpp")]


@pytest.fixture(scope="module")
def probe(tmp_path_factory: pytest.TempPathFactory) -> Path:
    compiler = shutil.which("clang++") or shutil.which("g++")
    if compiler is None:
        pytest.skip("no host C++ compiler")
    out = tmp_path_factory.mktemp("probe") / "checkdata_probe"
    subprocess.run(
        [compiler, "-std=c++17", "-Wall", "-Werror", "-O1", f"-I{REPO / 'game' / 'src'}",
         str(REPO / "tests" / "cpp" / "checkdata_probe.cpp"), *map(str, SOURCES), "-o", str(out)],
        check=True,
    )
    return out


def ask(probe: Path, *args: str, path: Path = CHECKDATA) -> list[str]:
    return subprocess.run([str(probe), str(path), *args], check=True, capture_output=True,
                          text=True).stdout.splitlines()


def test_summary(probe: Path) -> None:
    fields = dict(line.split("=", 1) for line in ask(probe, "summary"))
    assert fields["format"] == "1"
    assert fields["data_version"] == CAMPAIGN["data_version"]
    assert fields["hub"] == CAMPAIGN["hub_map"]
    assert int(fields["chapters"]) == len(CAMPAIGN["chapters"])
    assert int(fields["locations"]) == len(CAMPAIGN["locations"])


def test_every_map_has_its_chapter_and_reached_check(probe: Path) -> None:
    by_id = {l["id"]: l for l in CAMPAIGN["locations"]}
    for chapter in CAMPAIGN["chapters"]:
        for map_name in chapter["maps"]:
            assert ask(probe, "chapter_of", map_name) == [chapter["key"]]
            reached = int(ask(probe, "reached", map_name)[0])
            assert by_id[reached]["trigger"] == {"type": "map_reached", "map": map_name}
        complete = int(ask(probe, "complete", chapter["key"])[0])
        assert by_id[complete]["trigger"]["chapter"] == chapter["key"]
        assert ask(probe, "exits", chapter["key"]) == [f"{a}>{b}" for a, b in chapter["exits"]]
    assert ask(probe, "chapter_of", CAMPAIGN["hub_map"]) == [""]


def test_find_chapter(probe: Path) -> None:
    assert ask(probe, "find", "9a") == ["d2_prison_06"]
    assert ask(probe, "find", "route kanal") == ["d1_canals_01"]
    assert ask(probe, "find", "ravenholm") == [""]  # not a prefix of the name
    assert ask(probe, "find", "We dont go") == ["d1_town_01"]
    assert ask(probe, "find", "D1_Eli_01") == ["d1_eli_01"]


def test_pickups_and_gates(probe: Path) -> None:
    names = {l["name"]: l["id"] for l in CAMPAIGN["locations"]}
    assert int(ask(probe, "pickup", "weapon_pickup", "weapon_smg1")[0]) == names["First SMG"]
    assert int(ask(probe, "pickup", "item_pickup", "item_suit")[0]) == names["First HEV Suit"]
    assert int(ask(probe, "pickup", "weapon_upgrade", "weapon_physcannon")[0]) == \
        names["First Super Gravity Gun"]
    assert ask(probe, "pickup", "weapon_pickup", "weapon_stunstick") == ["0"]
    assert ask(probe, "gate", "weapon_physcannon") == ["Progressive Gravity Gun"]
    assert ask(probe, "gate", "item_battery") == [""]
    assert ask(probe, "stages", "Progressive Gravity Gun") == ["4"]
    assert ask(probe, "key", "d1_canals_06") == ["scripts/vehicles/airboat.txt|Water Hazard Boat Keys"]
    assert ask(probe, "key", "d1_eli_01") == [""]
    assert ask(probe, "upgrade", "Airboat Gun") == ["d1_canals_11", "d1_canals_13"]


def test_cold_load_kits(probe: Path) -> None:
    # d1_canals_01's suit and crowbar spawn only on a direct load; a template
    # copy carries an `&NNNN` suffix.
    assert ask(probe, "kit", "d1_canals_01", "start_item") == ["1"]
    assert ask(probe, "kit", "D1_Canals_01", "start_item&0000") == ["1"]
    assert ask(probe, "kit", "d1_canals_03", "global_newgame_spawner_suit") == ["1"]
    assert ask(probe, "kit", "d1_canals_03", "start_item") == ["0"]
    assert ask(probe, "kit", "d1_canals_01", "") == ["0"]


def test_chargers_carry_positions(probe: Path) -> None:
    expected = [l for l in CAMPAIGN["locations"]
                if l["trigger"]["type"] == "charger" and l["map"] == "d1_canals_06"]
    lines = ask(probe, "chargers", "d1_canals_06")
    assert len(lines) == len(expected)
    for line, entry in zip(lines, expected):
        id_, arg, *pos = line.split()
        assert int(id_) == entry["id"]
        assert arg == f"{entry['trigger']['classname']}@{entry['trigger']['at']}"
        assert [int(p) for p in pos] == entry["position"]


def test_other_format_refused(probe: Path, tmp_path: Path) -> None:
    other = tmp_path / "checkdata.txt"
    other.write_text("V|99\nD|x\n")
    assert ask(probe, "summary", path=other) == ["load=0"]

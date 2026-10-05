"""The game's half of the bridge against the client's half.

`game/src/ap_text`, `ap_state` and `ap_bridge` touch no engine code, so they
are built natively here with `tests/cpp/bridge_probe.cpp` and fed what
`client/bridge.py` writes. A drift between the two parsers shows up here rather
than as an unlock that silently never arrives in game.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "apworld" / "half_life_2"))

from client.bridge import Bridge  # noqa: E402

SOURCES = [REPO / "game" / "src" / name for name in ("ap_text.cpp", "ap_state.cpp", "ap_bridge.cpp")]


@pytest.fixture(scope="module")
def probe(tmp_path_factory: pytest.TempPathFactory) -> Path:
    compiler = shutil.which("clang++") or shutil.which("g++")
    if compiler is None:
        pytest.skip("no host C++ compiler")
    out = tmp_path_factory.mktemp("probe") / "bridge_probe"
    subprocess.run(
        [compiler, "-std=c++17", "-Wall", "-Werror", "-O1", f"-I{REPO / 'game' / 'src'}",
         str(REPO / "tests" / "cpp" / "bridge_probe.cpp"), *map(str, SOURCES), "-o", str(out)],
        check=True,
    )
    return out


def run(probe: Path, store: Path, *args: str) -> list[str]:
    result = subprocess.run([str(probe), str(store), *args], check=True, capture_output=True, text=True)
    return result.stdout.splitlines()


def parsed(lines: list[str]) -> dict[str, str]:
    """The first poll's fields; events collected under `events`."""
    fields: dict[str, str] = {}
    events: list[str] = []
    for line in lines[1:]:
        if line.startswith("poll="):
            break
        key, _, value = line.partition("=")
        if key == "event":
            events.append(value)
        else:
            fields[key] = value
    fields["events"] = "\n".join(events)
    return fields


def test_parses_a_full_snapshot(probe: Path, tmp_path: Path) -> None:
    bridge = Bridge(tmp_path)
    bridge.queue_event("ITEM", "Ammo Cache")
    bridge.queue_event("DEATHLINK", "PlayerTwo~a hunter")
    bridge.write_snapshot(
        connected=True,
        chapters=["d1_trainstation_01", "d1_canals_01"],
        items=["Shotgun", "Water Hazard Boat Keys", "Item, with comma"],
        death_link=True,
        death_link_amnesty=4,
        excluded=["d3_breen_01"],
        ungated=["item_battery"],
        starting=["weapon_crowbar", "weapon_physcannon"],
        counts={"Progressive Gravity Gun": 2, "Other: Thing": 1},
        checked=[8000001, 8000002],
        missing=[8000003],
        options={"gravity_gun_stage": 2, "melee_throw": True},
        data_version="d645439896ec",
        slot="Seed1234:3",
    )

    lines = run(probe, tmp_path, "poll")
    assert lines[0] == "poll=1"
    fields = parsed(lines)

    assert fields["session"] == bridge.session
    assert fields["slot"] == "Seed1234:3"
    assert fields["data_version"] == "d645439896ec"
    assert fields["connected"] == "1"
    assert fields["chapters"] == "d1_canals_01;d1_trainstation_01"
    assert fields["excluded"] == "d3_breen_01"
    assert fields["items"] == "Item, with comma;Shotgun;Water Hazard Boat Keys"
    assert fields["ungated"] == "item_battery"
    assert fields["starting"] == "weapon_crowbar;weapon_physcannon"
    assert fields["counts"] == "Other: Thing:1;Progressive Gravity Gun:2"
    assert fields["checked"] == "8000001;8000002"
    assert fields["missing"] == "8000003"
    # Options, including the fixed DeathLink keys, land in the generic map.
    assert fields["option.death_link"] == "1"
    assert fields["option.death_link_amnesty"] == "4"
    assert fields["option.gravity_gun_stage"] == "2"
    assert fields["option.melee_throw"] == "1"
    assert int(fields["now"]) > 0
    assert [e.split("|")[:3] for e in fields["events"].splitlines()] == [
        ["1", "ITEM", "Ammo Cache"],
        ["2", "DEATHLINK", "PlayerTwo~a hunter"],
    ]


def test_unchanged_snapshot_is_not_reparsed(probe: Path, tmp_path: Path) -> None:
    Bridge(tmp_path).write_snapshot(connected=True, chapters=[], items=[])
    assert [line for line in run(probe, tmp_path, "poll", "poll") if line.startswith("poll=")] == [
        "poll=1", "poll=0"]


def test_no_snapshot_reads_nothing(probe: Path, tmp_path: Path) -> None:
    assert run(probe, tmp_path, "poll") == ["poll=0"]


def test_disconnected_snapshot(probe: Path, tmp_path: Path) -> None:
    Bridge(tmp_path).write_snapshot(connected=False, chapters=[], items=[])
    fields = parsed(run(probe, tmp_path, "poll"))
    assert fields["connected"] == "0"
    assert fields["slot"] == ""


def test_game_lines_reach_the_client(probe: Path, tmp_path: Path) -> None:
    bridge = Bridge(tmp_path)
    run(probe, tmp_path, "send", "HELLO", "d1_trainstation_01")
    run(probe, tmp_path, "send", "CHAT", "Gordon", "hello there")
    run(probe, tmp_path, "send", "APTEST", "note", "")
    run(probe, tmp_path, "ack", "7")

    events = bridge.read_events()
    assert [(e.kind, e.args) for e in events] == [
        ("HELLO", ["d1_trainstation_01"]),
        ("CHAT", ["Gordon", "hello there"]),
        ("APTEST", ["note", ""]),
        ("ACK", ["7"]),
    ]

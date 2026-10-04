"""Scenario harness tests: groups, results, the dll swap, verbs. No game needed."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "aptest"))

import aptest  # noqa: E402
import checkdata  # noqa: E402
import groups as group_registry  # noqa: E402
from scenario import Context, Group, Scenario, reflow  # noqa: E402


@pytest.fixture
def ctx(tmp_path: Path) -> Context:
    return Context(store=tmp_path / "archipelago", game_root=None,
                   default_items={"HEV Suit": 1, "Progressive Gravity Gun": 4})


@pytest.fixture
def harness(ctx: Context) -> aptest.Harness:
    return aptest.Harness(ctx, group_registry.discover(), "foundation")


def said(h: aptest.Harness) -> str:
    return h.say_path.read_text(encoding="utf-8")


def test_groups_are_discovered() -> None:
    found = group_registry.discover()
    assert "foundation" in found
    assert list(found) == sorted(found)


@pytest.mark.parametrize("name", list(group_registry.discover()))
def test_every_group_builds_unique_titles(name: str, ctx: Context) -> None:
    group = group_registry.discover()[name]
    if group.needs_checkdata:
        ctx.checkdata = checkdata.parse(REPO_CHECKDATA)
    titles = [s.title for s in group.build(ctx)]
    assert titles and len(titles) == len(set(titles))


REPO_CHECKDATA = (HERE.parent / "apworld" / "half_life_2" / "mod" / "files"
                  / "archipelago" / "checkdata.txt")


def test_checkdata_parses_the_generated_file() -> None:
    data = checkdata.parse(REPO_CHECKDATA)
    assert data.format == 1 and data.data_version
    assert data.chapters[0].maps[0] == data.chapters[0].key
    assert data.chapters[-1].is_goal
    assert all(s.location in data.locations for s in data.sources)
    assert data.lockable["weapon_physcannon"] == "Progressive Gravity Gun"


def test_unproven_is_the_non_placed_subset() -> None:
    ctx = Context(store=Path("/nonexistent"), game_root=None,
                  checkdata=checkdata.parse(REPO_CHECKDATA))
    found = group_registry.discover()
    every = {s.title for s in found["sources"].build(ctx)}
    unproven = {s.title for s in found["unproven"].build(ctx)}
    assert unproven < every
    assert not any(t.endswith("(placed)") for t in unproven)


def test_foundation_needs_no_checkdata() -> None:
    assert not group_registry.discover()["foundation"].needs_checkdata


def test_alias_maps_to_the_current_group() -> None:
    groups = {"new": Group("new", "", lambda c: [], aliases=("old",))}
    assert group_registry.canonical("old", groups) == "new"
    assert group_registry.canonical("other", groups) == "other"


def test_reflow_joins_wrapped_sentences() -> None:
    assert reflow("One sentence\n  wrapped here.\nTwo.") == ["One sentence wrapped here.", "Two."]


def test_reflow_breaks_long_sentences() -> None:
    lines = reflow(("word " * 60).strip() + ".")
    assert all(len(l) <= 120 for l in lines) and len(lines) > 1


def test_start_writes_go_file_and_snapshot(harness: aptest.Harness) -> None:
    harness.command("next", "")
    go = harness.go_path.read_text(encoding="utf-8").splitlines()
    assert go[0].startswith("seq=") and go[1] == f"map={harness.scenarios[0].map}"
    snap = harness.bridge.in_path.read_text(encoding="utf-8")
    assert "Progressive Gravity Gun;Progressive Gravity Gun" in snap
    assert "slot=aptest:1" in snap


def test_redo_moves_the_sequence(harness: aptest.Harness) -> None:
    harness.command("next", "")
    first = harness.go_path.read_text().splitlines()[0]
    harness.command("redo", "")
    assert harness.go_path.read_text().splitlines()[0] != first


def test_setup_and_pos_reach_the_go_file(harness: aptest.Harness) -> None:
    index = next(i for i, s in enumerate(harness.scenarios) if s.setup and s.pos)
    harness.command("go", str(index))
    go = harness.go_path.read_text().splitlines()
    assert f"pos={harness.scenarios[index].pos}" in go
    assert [l[6:] for l in go if l.startswith("setup=")] == harness.scenarios[index].setup


def test_pass_records_and_moves_on(harness: aptest.Harness) -> None:
    harness.command("next", "")
    harness.command("pass", "fine")
    lines = harness.results_path.read_text().splitlines()
    assert lines[0].split("|")[2:4] == [harness.scenarios[0].title, "pass"]
    assert lines[0].split("|")[6] == "foundation"
    assert harness.current == 1


def test_fail_needs_a_note(harness: aptest.Harness) -> None:
    harness.command("next", "")
    harness.command("fail", "")
    assert not harness.results_path.exists()
    assert "needs a note" in said(harness)


def test_next_skips_tested_scenarios(harness: aptest.Harness) -> None:
    harness.command("go", "0")
    harness.command("pass", "")
    fresh = aptest.Harness(harness.ctx, harness.groups, "foundation")
    fresh.command("next", "")
    assert fresh.current == 1


def test_clear_drops_only_the_group(harness: aptest.Harness, tmp_path: Path) -> None:
    harness.command("next", "")
    harness.command("pass", "")
    with harness.results_path.open("a") as f:
        f.write("t|0|Other|pass||" "|othergroup\n")
    harness.command("clear", "")
    assert "!clear yes" in said(harness)
    harness.command("clear", "yes")
    remaining = harness.results_path.read_text().splitlines()
    assert remaining == ["t|0|Other|pass|||othergroup"]
    assert "foundation" in harness.results_path.with_name(aptest.CLEARED_NAME).read_text()


def test_give_and_take_count(harness: aptest.Harness) -> None:
    harness.command("next", "")
    harness.command("take", "progressive gravity gun")
    assert harness.items["Progressive Gravity Gun"] == 3
    harness.command("give", "Car Keys")
    assert harness.items["Car Keys"] == 1


def test_item_and_trap_queue_events(harness: aptest.Harness) -> None:
    harness.command("next", "")
    harness.command("item", "medkit")
    harness.command("trap", "headcrab")
    harness.command("item", "nonsense")
    snap = harness.bridge.in_path.read_text()
    assert "|ITEM|Medkit|" in snap and "|TRAP|Headcrab Trap|" in snap
    assert "No item 'nonsense'" in said(harness)


def test_deathlink_bypasses_the_window(harness: aptest.Harness) -> None:
    harness.command("deathlink", "")
    assert "|DEATHLINK|APTest~a test DeathLink|" in harness.bridge.in_path.read_text()


def test_connect_toggle(harness: aptest.Harness) -> None:
    harness.command("disconnect", "")
    assert "connected=0" in harness.bridge.in_path.read_text()
    harness.command("connect", "")
    assert "connected=1" in harness.bridge.in_path.read_text()


def test_group_switch_in_game(harness: aptest.Harness, monkeypatch) -> None:
    extra = Group("extra", "x", lambda c: [Scenario("only", "d1_trainstation_01")])
    harness.groups = {**harness.groups, "extra": extra}
    harness.command("group", "extra")
    assert harness.group == "extra" and len(harness.scenarios) == 1
    harness.command("group", "nope")
    assert harness.group == "extra"


def test_group_needing_checkdata_is_refused(harness: aptest.Harness) -> None:
    harness.groups = {**harness.groups,
                      "data": Group("data", "x", lambda c: [], needs_checkdata=True)}
    harness.command("group", "data")
    assert harness.group == "foundation"
    assert "needs checkdata.txt" in said(harness)


def test_game_events_are_handled(harness: aptest.Harness) -> None:
    harness.command("next", "")
    with harness.bridge.out_path.open("a") as f:
        f.write("APTEST|pass|ok\nCHECK|123\nDEATH|Gordon|a hunter|0\n")
    for event in harness.bridge.read_events():
        harness.handle(event)
    assert harness.results_path.exists()
    assert "Other check: 123" in said(harness)
    assert "DEATH: Gordon | a hunter | 0" in said(harness)


def test_unknown_verb_prints_help(harness: aptest.Harness) -> None:
    harness.command("bogus", "")
    assert said(harness).strip().endswith("!disconnect")


def test_dll_swap_round_trip(tmp_path: Path) -> None:
    installed = tmp_path / "bin" / "server.dll"
    installed.parent.mkdir()
    installed.write_bytes(b"retail")
    test_dll = tmp_path / "test.dll"
    test_dll.write_bytes(b"xx" + aptest.TEST_DLL_MARKER + b"xx")

    swap = aptest.DllSwap(installed, test_dll)
    assert swap.check() is None
    swap.swap_in()
    assert installed.read_bytes() == test_dll.read_bytes()
    swap.restore()
    assert installed.read_bytes() == b"retail" and not swap.backup.exists()


def test_dll_swap_keeps_an_old_backup(tmp_path: Path) -> None:
    """A backup left by a killed run is the real dll; never overwrite it."""
    installed = tmp_path / "server.dll"
    installed.write_bytes(b"test from last time")
    test_dll = tmp_path / "test.dll"
    test_dll.write_bytes(aptest.TEST_DLL_MARKER)
    swap = aptest.DllSwap(installed, test_dll)
    swap.backup.write_bytes(b"retail")
    swap.swap_in()
    swap.restore()
    assert installed.read_bytes() == b"retail"


def test_dll_swap_refuses_a_release_build(tmp_path: Path) -> None:
    installed = tmp_path / "server.dll"
    installed.write_bytes(b"retail")
    release = tmp_path / "release.dll"
    release.write_bytes(b"no marker here")
    assert "not a test build" in aptest.DllSwap(installed, release).check()


def test_stale_lock_is_ignored(tmp_path: Path) -> None:
    lock = tmp_path / "aptest.lock"
    lock.write_text("999999999")
    assert aptest.running_harness(lock) is None

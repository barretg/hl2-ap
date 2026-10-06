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
    found = group_registry.discover()
    if group_registry.needs_checkdata(name, found):
        ctx.checkdata = checkdata.parse(REPO_CHECKDATA)
    keys = [(s.origin, s.title) for s in group_registry.build(name, found, ctx)]
    assert keys and len(keys) == len(set(keys))


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
    assert "items=HEV Suit;Progressive Gravity Gun" in snap
    assert "starting=weapon_crowbar" in snap
    assert "slot=aptest:1" in snap


def test_counts_and_default_items_from_checkdata(ctx: Context) -> None:
    ctx.checkdata = checkdata.parse(REPO_CHECKDATA)
    ctx.default_items = aptest.default_items(ctx.checkdata)
    assert ctx.default_items["Progressive Gravity Gun"] == 4
    assert ctx.default_items["Water Hazard Boat Keys"] == 1
    assert ctx.default_items["Airboat Gun"] == 1
    assert ctx.default_items["Buggy Gun"] == 1
    assert ctx.default_items["Flashlight"] == 1
    harness = aptest.Harness(ctx, group_registry.discover(), "foundation")
    harness.command("next", "")
    assert "counts=Progressive Gravity Gun:4" in harness.bridge.in_path.read_text()


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


def test_next_revisits_failed_and_wraps(harness: aptest.Harness) -> None:
    harness.command("go", "0")
    harness.command("fail", "broken")
    harness.command("go", "1")
    harness.command("pass", "")
    for i in range(2, len(harness.scenarios)):
        harness.command("go", str(i))
        harness.command("note", "seen")
    harness.command("go", "1")
    harness.command("next", "")
    assert harness.current == 1
    assert "No open scenarios" in said(harness)
    # A later session comes back for the leftover fail.
    fresh = aptest.Harness(harness.ctx, harness.groups, "foundation")
    fresh.command("next", "")
    assert fresh.current == 0
    fresh.command("pass", "")
    fresh.command("next", "")
    assert fresh.current == 0
    assert "No open scenarios" in said(fresh)


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
    harness.command("give", "Buggy Keys")
    assert harness.items["Buggy Keys"] == 1


def test_item_and_trap_queue_events(harness: aptest.Harness) -> None:
    harness.command("next", "")
    harness.command("item", "medkit")
    harness.command("trap", "headcrab")
    harness.command("item", "nonsense")
    snap = harness.bridge.in_path.read_text()
    assert "|ITEM|Medkit|" in snap
    assert "No trap 'headcrab'" in said(harness)  # none in this build
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
    assert "DEATH: Gordon | a hunter -> sent" in said(harness)
    assert "[aptest] DeathLink sent" in said(harness)


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


def composite_groups() -> dict[str, Group]:
    def make(*titles: str, origin: str = ""):
        return lambda ctx: [Scenario(title=t, map="m", origin=origin) for t in titles]
    return {
        "base": Group("base", "x", make("b1", "b2")),
        "view": Group("view", "x", make("b2", origin="base")),
        "phase": Group("phase", "x", make("p1"), includes=("base", "view")),
    }


def test_included_groups_follow_own_scenarios_once(ctx: Context) -> None:
    groups = composite_groups()
    built = group_registry.build("phase", groups, ctx)
    assert [(s.origin, s.title) for s in built] == [
        ("phase", "p1"), ("base", "b1"), ("base", "b2")]


def test_include_cycles_and_unknowns_are_refused() -> None:
    groups = {"a": Group("a", "x", lambda c: [], includes=("b",)),
              "b": Group("b", "x", lambda c: [], includes=("a",))}
    with pytest.raises(ValueError, match="include each other"):
        group_registry._members("a", groups, ())


def test_needs_checkdata_through_includes() -> None:
    groups = {"a": Group("a", "x", lambda c: [], includes=("b",)),
              "b": Group("b", "x", lambda c: [], needs_checkdata=True)}
    assert group_registry.needs_checkdata("a", groups)


def test_verdicts_shared_with_origin_group(ctx: Context) -> None:
    h = aptest.Harness(ctx, composite_groups(), "phase")
    h.command("go", "2")  # base's b2, run from the phase group
    h.command("pass", "")
    assert h.counts("base")["pass"] == 1
    assert h.counts("view")["pass"] == 1
    assert h.results_path.read_text().strip().endswith("|base")


def test_clearing_a_phase_clears_its_subgroups_verdicts(ctx: Context) -> None:
    h = aptest.Harness(ctx, composite_groups(), "phase")
    h.command("go", "0")
    h.command("pass", "")
    h.command("pass", "")  # moved on to base's b1
    h.command("clear", "yes")
    assert h.counts("phase") == {"untested": 3}


def test_phase2_includes_sources() -> None:
    found = group_registry.discover()
    assert found["phase2"].includes == ("sources", "unproven")
    ctx = Context(store=Path("/nonexistent"), game_root=None,
                  checkdata=checkdata.parse(REPO_CHECKDATA))
    built = group_registry.build("phase2", found, ctx)
    sources = group_registry.build("sources", found, ctx)
    assert built[0].origin == "phase2"
    assert [(s.origin, s.title) for s in built[1:]] == [(s.origin, s.title) for s in sources]


def test_sources_name_the_pickup_not_the_item() -> None:
    ctx = Context(store=Path("/nonexistent"), game_root=None,
                  checkdata=checkdata.parse(REPO_CHECKDATA))
    built = group_registry.build("sources", group_registry.discover(), ctx)
    gravity = [s for s in built if s.title.startswith("First Gravity Gun")]
    assert gravity and all("Progressive" not in s.steps for s in gravity)
    assert all("Gravity Gun" in s.steps for s in gravity)


def test_drop_scenarios_arm_the_tester_without_the_tested_weapon() -> None:
    ctx = Context(store=Path("/nonexistent"), game_root=None,
                  checkdata=checkdata.parse(REPO_CHECKDATA))
    built = group_registry.build("sources", group_registry.discover(), ctx)
    drops = [s for s in built if s.title.endswith("(drop)")]
    assert drops
    for s in drops:
        assert "give weapon_crowbar" in s.setup
        tested = s.title.split(":")[0].removeprefix("First ")
        assert not (tested == "Shotgun" and "give weapon_shotgun" in s.setup)
    assert all("give weapon_crowbar" not in s.setup
               for s in built if s.title.endswith("(placed)"))


def test_templated_sources_are_spawned_by_setup() -> None:
    data = checkdata.parse(REPO_CHECKDATA)
    ctx = Context(store=Path("/nonexistent"), game_root=None, checkdata=data)
    built = group_registry.build("sources", group_registry.discover(), ctx)
    by_map_pos = {(s.map, s.pos): s for s in built}
    templated = [src for src in data.sources if src.spawner]
    assert templated
    for src in templated:
        scenario = by_map_pos[(src.map, src.position)]
        name, _, input_name = src.spawner.partition(",")
        assert scenario.setup[0] == "sv_cheats 1"
        assert scenario.setup[-2:] == ["notarget", f"ent_fire {name} {input_name}"]

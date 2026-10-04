"""Bridge protocol tests. These need neither Half-Life 2 nor an Archipelago server."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apworld" / "half_life_2"))

from client.bridge import (  # noqa: E402
    MAX_PENDING_IN_SNAPSHOT,
    Bridge,
    GameEvent,
    sanitise,
    store_dir,
)


@pytest.fixture
def bridge(tmp_path: Path) -> Bridge:
    return Bridge(tmp_path)


def snapshot(bridge: Bridge, **overrides) -> bool:
    kwargs = dict(
        connected=True,
        chapters=["d1_trainstation_01"],
        items=["Shotgun"],
    )
    kwargs.update(overrides)
    return bridge.write_snapshot(**kwargs)


def test_reads_complete_lines_only(bridge: Bridge) -> None:
    bridge.out_path.write_text("CHECK|7760001\nCHECK|7760002\nCHECK|776", encoding="utf-8")

    events = bridge.read_events()

    assert [e.kind for e in events] == ["CHECK", "CHECK"]
    assert [e.arg for e in events] == ["7760001", "7760002"]

    # The truncated third line is picked up once the game finishes writing it.
    with bridge.out_path.open("a", encoding="utf-8") as handle:
        handle.write("0003\n")
    assert [e.arg for e in bridge.read_events()] == ["7760003"]


def test_cursor_survives_repeated_polls(bridge: Bridge) -> None:
    bridge.out_path.write_text("CHECK|1\n", encoding="utf-8")
    assert len(bridge.read_events()) == 1
    assert bridge.read_events() == []


def test_truncated_log_restarts_the_cursor(bridge: Bridge) -> None:
    """A fresh game session truncates ap_out.txt; we must not skip its events."""
    bridge.out_path.write_text("CHECK|1\nCHECK|2\nCHECK|3\n", encoding="utf-8")
    bridge.read_events()

    bridge.out_path.write_text("CHECK|9\n", encoding="utf-8")
    assert [e.arg for e in bridge.read_events()] == ["9"]


def test_reset_cursor_skips_existing_log(bridge: Bridge) -> None:
    bridge.out_path.write_text("CHECK|1\n", encoding="utf-8")
    bridge.reset_cursor()
    assert bridge.read_events() == []


def test_snapshot_is_skipped_when_unchanged(bridge: Bridge) -> None:
    assert snapshot(bridge) is True
    assert snapshot(bridge) is False
    assert snapshot(bridge, items=["Shotgun", "RPG"]) is True


def test_snapshot_contents(bridge: Bridge) -> None:
    snapshot(bridge, chapters=["d1_trainstation_01", "d1_canals_01"], items=["RPG", "Shotgun"])
    text = bridge.in_path.read_text(encoding="utf-8")

    assert "connected=1" in text
    assert "chapters=d1_canals_01,d1_trainstation_01" in text
    # Item names are semicolon separated because names may contain commas.
    assert "items=RPG;Shotgun" in text
    assert "now=" in text


def test_snapshot_carries_excluded_missions(bridge: Bridge) -> None:
    """"Not in this seed" has to be distinguishable from "locked"."""
    snapshot(bridge)
    assert "excluded=\n" in bridge.in_path.read_text(encoding="utf-8")

    assert snapshot(bridge, excluded=["d1_trainstation_00"]) is True
    assert "excluded=d1_trainstation_00" in bridge.in_path.read_text(encoding="utf-8")


def test_snapshot_carries_the_starting_weapons(bridge: Bridge) -> None:
    """What the seed opens with, and what the game must never take away."""
    snapshot(bridge)
    assert "starting=\n" in bridge.in_path.read_text(encoding="utf-8")

    assert snapshot(bridge, starting=["weapon_crowbar"]) is True
    text = bridge.in_path.read_text(encoding="utf-8")
    # Not sorted: this is the seed's list, in its own order.
    assert "starting=weapon_crowbar" in text


def test_snapshot_carries_ungated_classnames(bridge: Bridge) -> None:
    """"Not gated at all" has to be distinguishable from "gated and owned"."""
    snapshot(bridge)
    assert "ungated=\n" in bridge.in_path.read_text(encoding="utf-8")

    assert snapshot(bridge, ungated=["item_suit"]) is True
    text = bridge.in_path.read_text(encoding="utf-8")
    assert "ungated=item_suit" in text
    # Classnames are semicolon separated, matching `items`.
    assert snapshot(bridge, ungated=["item_battery", "item_suit"]) is True
    assert "ungated=item_battery;item_suit" in bridge.in_path.read_text(encoding="utf-8")


def test_snapshot_carries_the_deathlink_amnesty(bridge: Bridge) -> None:
    """The game counts the allowance down, so it has to be told what it is."""
    snapshot(bridge)
    assert "death_link_amnesty=0" in bridge.in_path.read_text(encoding="utf-8")

    assert snapshot(bridge, death_link_amnesty=4) is True
    assert "death_link_amnesty=4" in bridge.in_path.read_text(encoding="utf-8")


def test_snapshot_amnesty_is_never_negative(bridge: Bridge) -> None:
    snapshot(bridge, death_link_amnesty=-3)
    assert "death_link_amnesty=0" in bridge.in_path.read_text(encoding="utf-8")


def test_snapshot_carries_a_session_id(bridge: Bridge) -> None:
    snapshot(bridge)
    assert f"session={bridge.session}" in bridge.in_path.read_text(encoding="utf-8")


def test_sessions_differ_between_client_runs(tmp_path: Path) -> None:
    """The game keys its event high-water mark on this."""
    assert Bridge(tmp_path).session != Bridge(tmp_path).session


def test_snapshot_carries_the_slot(bridge: Bridge) -> None:
    """What the game resets its run on, which the session cannot answer."""
    snapshot(bridge, slot="Seed1234:3")
    assert "slot=Seed1234:3" in bridge.in_path.read_text(encoding="utf-8")


def test_snapshot_slot_is_empty_while_disconnected(bridge: Bridge) -> None:
    """No slot is "no news" to the game, not "a new run"."""
    snapshot(bridge)
    assert "slot=" in bridge.in_path.read_text(encoding="utf-8")


def test_a_changed_slot_rewrites_the_snapshot(bridge: Bridge) -> None:
    """Same length, different run: the write must not be skipped as unchanged."""
    assert snapshot(bridge, slot="Seed1234:3")
    assert snapshot(bridge, slot="Seed1234:4")


def test_equal_length_changes_are_still_written(bridge: Bridge) -> None:
    """A flag flip does not change the snapshot's length.

    The game used to compare file size and would freeze on a stale snapshot,
    so this asserts the two states are genuinely distinguishable by content.
    """
    snapshot(bridge, connected=True)
    first = bridge.in_path.read_text(encoding="utf-8")

    assert snapshot(bridge, connected=False) is True
    second = bridge.in_path.read_text(encoding="utf-8")

    assert "connected=1" in first
    assert "connected=0" in second
    assert first != second


def test_pending_event_survives_until_acknowledged(bridge: Bridge) -> None:
    event = bridge.queue_event("ITEM", "Ammo Cache")
    snapshot(bridge)

    assert f"event={event.seq}|ITEM|Ammo Cache|" in bridge.in_path.read_text(encoding="utf-8")

    # Still there while unacknowledged, even though nothing else changed.
    snapshot(bridge)
    assert "event=" in bridge.in_path.read_text(encoding="utf-8")

    bridge.acknowledge(event.seq)
    assert bridge.pending_count == 0
    snapshot(bridge, force=True)
    assert "event=" not in bridge.in_path.read_text(encoding="utf-8")


def pending_lines(bridge: Bridge) -> list[str]:
    return [
        line for line in bridge.in_path.read_text(encoding="utf-8").splitlines()
        if line.startswith("event=")
    ]


def test_snapshot_is_not_rewritten_while_pending_is_unchanged(bridge: Bridge) -> None:
    """The write amplifier: rewriting every poll made the game re-ACK the lot."""
    bridge.queue_event("ITEM", "Ammo Cache")
    assert snapshot(bridge) is True
    assert snapshot(bridge) is False
    assert snapshot(bridge) is False


def test_snapshot_is_rewritten_when_pending_changes(bridge: Bridge) -> None:
    first = bridge.queue_event("ITEM", "Ammo Cache")
    snapshot(bridge)

    bridge.acknowledge(first.seq)
    assert snapshot(bridge) is True


def test_flood_is_windowed_not_dropped(bridge: Bridge) -> None:
    for index in range(300):
        bridge.queue_event("ITEM", f"Item {index}")

    assert bridge.queued_count == 300
    assert bridge.pending_count == MAX_PENDING_IN_SNAPSHOT

    snapshot(bridge)
    assert len(pending_lines(bridge)) == MAX_PENDING_IN_SNAPSHOT


def test_flood_drains_completely(bridge: Bridge) -> None:
    """Every queued item must eventually reach the game."""
    total = 300
    for index in range(total):
        bridge.queue_event("ITEM", f"Item {index}")

    delivered: list[int] = []
    for _ in range(total * 2):  # generous bound; must finish well inside it
        if bridge.queued_count == 0:
            break
        for seq in list(bridge._pending):
            delivered.append(seq)
            bridge.acknowledge(seq)

    assert bridge.queued_count == 0
    assert len(delivered) == total
    assert delivered == sorted(delivered)  # oldest first, in order


def test_acknowledging_refills_the_window(bridge: Bridge) -> None:
    for index in range(MAX_PENDING_IN_SNAPSHOT + 5):
        bridge.queue_event("ITEM", f"Item {index}")

    first = min(bridge._pending)
    bridge.acknowledge(first)

    assert bridge.pending_count == MAX_PENDING_IN_SNAPSHOT


def test_deathlink_skips_the_queue(bridge: Bridge) -> None:
    """A DeathLink stuck behind a flood would go stale and never fire."""
    for index in range(300):
        bridge.queue_event("ITEM", f"Item {index}")

    death = bridge.queue_event("DEATHLINK", "PlayerOne~a hunter")
    snapshot(bridge)

    assert any(f"event={death.seq}|DEATHLINK" in line for line in pending_lines(bridge))


def test_chat_skips_the_queue(bridge: Bridge) -> None:
    for index in range(300):
        bridge.queue_event("ITEM", f"Item {index}")

    chat = bridge.queue_event("CHAT", "[AP] hello")
    snapshot(bridge)

    assert any(f"event={chat.seq}|CHAT" in line for line in pending_lines(bridge))


def test_event_sequence_numbers_are_monotonic(bridge: Bridge) -> None:
    first = bridge.queue_event("ITEM", "Medkit")
    second = bridge.queue_event("DEATHLINK", "someone~a headcrab")
    assert second.seq > first.seq

    bridge.acknowledge(first.seq)
    third = bridge.queue_event("ITEM", "Armor Battery")
    assert third.seq > second.seq


def test_deathlink_payload_avoids_the_field_separator(bridge: Bridge) -> None:
    """The game splits an event line on '|', so payload fields use '~'."""
    bridge.queue_event("DEATHLINK", "PlayerOne~a hunter")
    snapshot(bridge)

    line = next(
        l for l in bridge.in_path.read_text(encoding="utf-8").splitlines()
        if l.startswith("event=")
    )
    assert line.count("|") == 3
    assert "PlayerOne~a hunter" in line


def test_snapshot_write_is_atomic(bridge: Bridge) -> None:
    snapshot(bridge)
    assert not list(bridge.dir.glob("*.tmp"))


def test_snapshot_survives_a_locked_destination(bridge: Bridge, monkeypatch) -> None:
    """Windows refuses os.replace while the game has ap_in.txt open.

    Letting that propagate killed the client's watcher task, which then sat
    there looking connected while delivering nothing.
    """
    def always_locked(src, dst):
        raise PermissionError(32, "in use by another process")

    monkeypatch.setattr("client.bridge.os.replace", always_locked)
    monkeypatch.setattr("client.bridge.REPLACE_RETRY_DELAY", 0)

    snapshot(bridge, items=["Shotgun"])

    assert "items=Shotgun" in bridge.in_path.read_text(encoding="utf-8")
    assert not list(bridge.dir.glob("*.tmp"))


def test_snapshot_retries_before_falling_back(bridge: Bridge, monkeypatch) -> None:
    calls = {"n": 0}
    real_replace = os.replace

    def flaky(src, dst):
        calls["n"] += 1
        if calls["n"] < 3:
            raise PermissionError(32, "in use by another process")
        return real_replace(src, dst)

    monkeypatch.setattr("client.bridge.os.replace", flaky)
    monkeypatch.setattr("client.bridge.REPLACE_RETRY_DELAY", 0)

    snapshot(bridge)

    assert calls["n"] == 3
    assert not list(bridge.dir.glob("*.tmp"))


def test_clear_log_removes_a_stale_temp(bridge: Bridge) -> None:
    """A leftover .tmp is the visible symptom of a previous crashed publish."""
    stale = bridge.in_path.with_suffix(".tmp")
    stale.write_text("half written", encoding="utf-8")

    bridge.clear_log()

    assert not stale.exists()


def test_clear_log_resets_cursor(bridge: Bridge) -> None:
    bridge.out_path.write_text("CHECK|1\n", encoding="utf-8")
    bridge.read_events()
    bridge.clear_log()
    bridge.out_path.write_text("CHECK|2\n", encoding="utf-8")
    assert [e.arg for e in bridge.read_events()] == ["2"]


def test_snapshot_options_are_sorted_lines(bridge: Bridge) -> None:
    """Seed settings ride as plain key=value lines, so new ones need no bridge change."""
    snapshot(bridge, options={"melee_throw": True, "butterfingers_reissue": False, "gravity_gun_stage": 2})
    lines = bridge.in_path.read_text(encoding="utf-8").splitlines()
    opts = [l for l in lines if l.split("=")[0] in ("melee_throw", "butterfingers_reissue", "gravity_gun_stage")]
    assert opts == ["butterfingers_reissue=0", "gravity_gun_stage=2", "melee_throw=1"]


def test_an_option_change_rewrites_the_snapshot(bridge: Bridge) -> None:
    assert snapshot(bridge, options={"melee_throw": False})
    assert not snapshot(bridge, options={"melee_throw": False})
    assert snapshot(bridge, options={"melee_throw": True})


@pytest.mark.parametrize("key", ["items", "event", "now", "Bad", "has space", ""])
def test_options_cannot_shadow_core_keys(bridge: Bridge, key: str) -> None:
    with pytest.raises(ValueError):
        snapshot(bridge, options={key: 1})


def test_option_text_is_sanitised(bridge: Bridge) -> None:
    snapshot(bridge, options={"label": "a|b\nc"})
    assert "label=a b c" in bridge.in_path.read_text(encoding="utf-8")


def test_sanitise_strips_separators() -> None:
    assert sanitise("Gordon|Freeman\r\nhi") == "Gordon Freeman  hi"


def test_reads_multibyte_text_without_losing_its_place(bridge: Bridge) -> None:
    """The cursor counts bytes; a non-ASCII chat line must not skew it."""
    bridge.out_path.write_bytes("CHAT|Alyx|caf\u00e9\nCHECK|1\n".encode("utf-8"))
    assert [e.kind for e in bridge.read_events()] == ["CHAT", "CHECK"]
    with bridge.out_path.open("ab") as handle:
        handle.write(b"CHECK|2\n")
    assert bridge.read_events() == [GameEvent("CHECK", ["2"])]


def test_store_dir_is_inside_the_mod_folder(tmp_path: Path) -> None:
    assert store_dir(tmp_path / "hl2ap") == tmp_path / "hl2ap" / "archipelago"

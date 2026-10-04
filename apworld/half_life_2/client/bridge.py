"""The file bridge, with no Archipelago dependency.

Keeping this importable on its own is what lets `tests/test_bridge.py` exercise
the whole protocol with no game and no server running. See docs/protocol.md.

Directions:
    ap_out.txt  game -> here, append-only. We keep a byte cursor so a restart
                does not replay the log and a partially written final line is
                left for the next poll.
    ap_in.txt   here -> game, a full snapshot rewritten on every change. One-shot
                deliveries ride along as `event=` lines until the game ACKs them.
"""

from __future__ import annotations

import os
import re
import time
import uuid
from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

CHECKDATA_NAME = "checkdata.txt"
IN_NAME = "ap_in.txt"
OUT_NAME = "ap_out.txt"

# The bridge directory inside the mod folder. Spelled out here rather than
# imported from the `mod` package so this module depends on nothing but the
# standard library; tests/test_mod_install.py checks the two agree.
STORE_SUBDIR = "archipelago"

# How many un-acked events may sit in the snapshot at once.
#
# Finishing a game releases every remaining item at once, which can be hundreds
# of filler grants. Writing them all into every snapshot made the game reparse
# and re-ACK the whole backlog several times a second (HL1), which saturated the
# bridge. The rest wait in a backlog and drain a window at a time.
MAX_PENDING_IN_SNAPSHOT = 16

# Kinds that bypass the window. Both are time-sensitive and tiny: the game
# discards a DeathLink older than ten seconds, and late chat is useless.
PRIORITY_KINDS = frozenset({"DEATHLINK", "CHAT"})

# How hard to try the atomic rename before writing in place instead.
REPLACE_ATTEMPTS = 5
REPLACE_RETRY_DELAY = 0.02

# Snapshot keys the bridge writes itself. `options` may not reuse them.
CORE_KEYS = frozenset({
    "session", "slot", "data_version", "connected", "death_link",
    "death_link_amnesty", "chapters", "excluded", "items", "ungated",
    "starting", "checked", "missing", "now", "event",
})

_OPTION_KEY = re.compile(r"^[a-z][a-z0-9_]*$")


def sanitise(text: str) -> str:
    """Strip what would break a line or a field: `|` and line breaks.

    For operator-controlled text only (player names, chat). The game side does
    the same to what it writes.
    """
    return re.sub(r"[|\r\n]", " ", text)


def store_dir(mod_dir: str | os.PathLike[str]) -> Path:
    """The bridge directory of a mod folder (`mod.install` returns that folder)."""
    return Path(mod_dir) / STORE_SUBDIR


@dataclass
class GameEvent:
    """One line the game wrote to ap_out.txt."""

    kind: str
    args: list[str]

    @property
    def arg(self) -> str:
        return self.args[0] if self.args else ""


@dataclass
class PendingEvent:
    """A one-shot delivery, held in the snapshot until the game ACKs it."""

    seq: int
    kind: str
    payload: str
    stamp: float = field(default_factory=time.time)

    def render(self) -> str:
        return f"event={self.seq}|{self.kind}|{self.payload}|{self.stamp:.0f}"


def _option_value(value: object) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    return sanitise(str(value))


class Bridge:
    """Both halves of the file protocol."""

    def __init__(self, store: str | os.PathLike[str]) -> None:
        self.dir = Path(store)
        self.out_path = self.dir / OUT_NAME
        self.in_path = self.dir / IN_NAME

        self._cursor = 0
        self._seq = 0
        # Events visible to the game, and the queue waiting behind them.
        # Nothing is discarded: the backlog drains as the game acknowledges.
        self._pending: dict[int, PendingEvent] = {}
        self._backlog: deque[PendingEvent] = deque()
        self._last_snapshot = ""
        self._last_pending: tuple[int, ...] = ()
        # Identifies this run of the client. The event sequence restarts from 1
        # on every launch, so the game resets its high-water mark when this
        # changes, or fresh events would look already applied.
        self.session = uuid.uuid4().hex[:8]

    # -- game -> client --------------------------------------------------

    def reset_cursor(self) -> None:
        """Skip whatever is already in the log, so a previous run is not replayed."""
        self._cursor = self.out_path.stat().st_size if self.out_path.exists() else 0

    def read_events(self) -> list[GameEvent]:
        """Consume new complete lines from ap_out.txt."""
        if not self.out_path.exists():
            return []

        size = self.out_path.stat().st_size
        if size < self._cursor:
            # Truncated: a fresh game session. Start over.
            self._cursor = 0
        if size == self._cursor:
            return []

        with self.out_path.open("rb") as handle:
            handle.seek(self._cursor)
            chunk = handle.read()
        # Only advance past whole lines, so a line the game is midway through
        # writing is picked up whole on the next poll.
        consumed = chunk.rfind(b"\n")
        if consumed < 0:
            return []
        self._cursor += consumed + 1
        text = chunk[: consumed + 1].decode("utf-8", errors="replace")

        events: list[GameEvent] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("|")
            events.append(GameEvent(parts[0], parts[1:]))
        return events

    # -- client -> game --------------------------------------------------

    def queue_event(self, kind: str, payload: str) -> PendingEvent:
        """Queue a one-shot delivery. Never dropped, only metered."""
        self._seq += 1
        event = PendingEvent(self._seq, kind, payload)
        if kind in PRIORITY_KINDS:
            # Straight into the snapshot, over the cap if need be.
            self._pending[event.seq] = event
        else:
            self._backlog.append(event)
            self._fill_window()
        return event

    def acknowledge(self, seq: int) -> None:
        """The game has applied this event; make room for the next one."""
        if self._pending.pop(seq, None) is not None:
            self._fill_window()

    def _fill_window(self) -> None:
        while self._backlog and len(self._pending) < MAX_PENDING_IN_SNAPSHOT:
            event = self._backlog.popleft()
            self._pending[event.seq] = event

    @property
    def pending_count(self) -> int:
        """Events visible to the game right now."""
        return len(self._pending)

    @property
    def queued_count(self) -> int:
        """Everything still owed to the game, in flight or waiting."""
        return len(self._pending) + len(self._backlog)

    def write_snapshot(
        self,
        *,
        connected: bool,
        chapters: Iterable[str],
        items: Iterable[str],
        death_link: bool = False,
        death_link_amnesty: int = 0,
        excluded: Iterable[str] = (),
        ungated: Iterable[str] = (),
        starting: Iterable[str] = (),
        checked: Iterable[int] = (),
        missing: Iterable[int] = (),
        options: Mapping[str, object] | None = None,
        data_version: str = "",
        slot: str = "",
        force: bool = False,
    ) -> bool:
        """Rewrite ap_in.txt. Returns True if anything was written.

        Written only when something the game cares about changed: the state, or
        which events are in flight. Never just because `now=` moved.

        `options` carries the seed's settings the game acts on (e.g.
        `melee_throw`), one `key=value` line each, sorted. Booleans become 1/0.
        Adding an option therefore needs no change here or in the harness.
        """
        opts = dict(options or {})
        for key in opts:
            if key in CORE_KEYS or not _OPTION_KEY.match(key):
                raise ValueError(f"bad snapshot option key {key!r}")

        lines = [
            "# Written by the Half-Life 2 Archipelago client.",
            f"session={self.session}",
            # Which slot of which seed: what the game resets its run on. Empty
            # while disconnected, which the game reads as "no news".
            f"slot={slot}",
            # The game refuses to send checks if this disagrees with its own
            # checkdata.txt, since the two would number locations differently.
            f"data_version={data_version}",
            f"connected={1 if connected else 0}",
            f"death_link={1 if death_link else 0}",
            # Counted down by the game: the death message names what is left.
            f"death_link_amnesty={max(0, int(death_link_amnesty))}",
            # Open missions, finales included (a finale is open when listed).
            "chapters=" + ",".join(sorted(chapters)),
            # Missions not in this seed at all, distinct from locked.
            "excluded=" + ",".join(sorted(excluded)),
            # Item names may contain commas, so `;`.
            "items=" + ";".join(sorted(items)),
            # Classnames this seed does not gate: neither granted nor refused.
            "ungated=" + ";".join(sorted(ungated)),
            # What the run opens with, in the seed's order. Empty means "use
            # checkdata.txt", never "start with nothing".
            "starting=" + ";".join(starting),
            # Between them, which locations the seed contains (for the tracker).
            "checked=" + ",".join(str(i) for i in checked),
            "missing=" + ",".join(str(i) for i in missing),
        ]
        lines += [f"{key}={_option_value(opts[key])}" for key in sorted(opts)]
        body = "\n".join(lines)
        pending = tuple(sorted(self._pending))

        if body == self._last_snapshot and pending == self._last_pending and not force:
            return False

        self._last_snapshot = body
        self._last_pending = pending

        full = [body, f"now={time.time():.0f}"]
        full += [self._pending[seq].render() for seq in pending]

        self.dir.mkdir(parents=True, exist_ok=True)
        self._publish("\n".join(full) + "\n")
        return True

    def _publish(self, text: str) -> None:
        """Write the snapshot without leaving a half-written file visible.

        A temp file and a rename. On Windows (and Wine) the rename fails while
        the game has ap_in.txt open, so retry briefly, then write in place: a
        torn read is transient, a failed write freezes the bridge.
        """
        temp = self.in_path.with_suffix(".tmp")
        temp.write_text(text, encoding="utf-8")
        for attempt in range(REPLACE_ATTEMPTS):
            try:
                os.replace(temp, self.in_path)
                return
            except PermissionError:
                if attempt < REPLACE_ATTEMPTS - 1:
                    time.sleep(REPLACE_RETRY_DELAY)
        self.in_path.write_text(text, encoding="utf-8")
        temp.unlink(missing_ok=True)

    def clear_log(self) -> None:
        """Truncate ap_out.txt, e.g. when starting a fresh session."""
        self.dir.mkdir(parents=True, exist_ok=True)
        self.out_path.write_text("", encoding="utf-8")
        self._cursor = 0
        # A leftover .tmp means a previous session died mid-publish.
        self.in_path.with_suffix(".tmp").unlink(missing_ok=True)

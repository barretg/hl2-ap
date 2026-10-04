"""APTest: an in-game scenario harness for Half-Life 2 Archipelago.

Stands in for the Python client and is driven entirely from the game. Start it
in a terminal and leave it: each scenario writes the snapshot the client would
(`ap_in.txt`), and the game loads the scenario's map, puts you at its spot and
runs its setup commands on its own. What the harness has to say appears on
screen. Verdicts and every check the game sends go to `aptest_results.txt`.

Needs the test build of the dll (`cmake --build build/game-test`, configured
with -DHL2AP_TEST_BUILD=ON), the only one that answers these. The harness swaps
it into the installed mod on start and puts the original back when it stops, so
start it before the game. Close the real client first: both write `ap_in.txt`.

In game, in chat (or `ap_test <verb>` in the console):
    !next              start the first untested scenario, then the one after
    !pass [note]       record a verdict; the next untested scenario loads
    !fail <note>
    !note <text>       a finding that is not pass or fail
    !redo / !prev / !go <n>
    !tp                back to the scenario's spot
    !info / !status / !list [text]
    !groups / !group <name>        list groups, or switch to another
    !give <item> / !take <item>    change what the snapshot holds
    !item <name> / !trap <name> / !deathlink   deliveries, as the client would
    !connect / !disconnect         what the snapshot says about the client
    !clear [yes]       drop this group's verdicts (kept in aptest_results_cleared.txt)

The same verbs, without the `!`, can be typed into the terminal.

Scenario groups are modules in tests/aptest/groups/ (see scenario.py).

Usage:
    python tests/aptest/aptest.py --list-groups
    python tests/aptest/aptest.py --group foundation
    python tests/aptest/aptest.py --group foundation --clear
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import sys
import threading
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "apworld" / "half_life_2"))

import groups as group_registry  # noqa: E402
import mod  # noqa: E402
from client import bridge as bridge_module  # noqa: E402
from scenario import Context, Group, Scenario, reflow  # noqa: E402

# The test build of the server dll, swapped into the installed mod while the
# harness runs. The marker is a string only the test build carries.
TEST_DLL = REPO / "build" / "game-test" / "server.dll"
TEST_DLL_MARKER = b"ap_test"

# Deliveries the harness accepts for `!item` / `!trap`. Placeholders until the
# item table exists (plan Phase 3); the game ignores names it does not know.
FILLER = ["Ammo Cache", "Medkit", "Battery"]
TRAPS = ["Headcrab Trap", "Butterfingers Trap", "Sticky Key Trap", "Reload Trap"]

RESULTS_NAME = "aptest_results.txt"
CLEARED_NAME = "aptest_results_cleared.txt"
GO_NAME = "aptest_go.txt"
SAY_NAME = "aptest_say.txt"
LOCK_NAME = "aptest.lock"

HELP = ("[aptest] !pass !fail !note !next !prev !redo !go <n> !info !status !list "
        "!groups !group <name> !clear !give !take !tp !item !trap !deathlink "
        "!connect !disconnect")


# -------------------------------------------------------------- results


def read_results(path: Path) -> list[list[str]]:
    if not path.exists():
        return []
    return [line.split("|") for line in path.read_text(encoding="utf-8").splitlines() if line]


def latest_verdicts(path: Path, group: str, groups: dict[str, Group]) -> dict[str, str]:
    """`{title: verdict}` for one group, the last verdict per title winning."""
    verdicts: dict[str, str] = {}
    for parts in read_results(path):
        if len(parts) >= 7 and group_registry.canonical(parts[6], groups) == group:
            verdicts[parts[2]] = parts[3]
    return verdicts


def clear_results(path: Path, group: str, groups: dict[str, Group]) -> int:
    """Drop one group's verdicts into the cleared file. Returns how many went."""
    if not path.exists():
        return 0
    kept: list[str] = []
    dropped: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split("|")
        ours = len(parts) >= 7 and group_registry.canonical(parts[6], groups) == group
        (dropped if ours else kept).append(line)
    if dropped:
        with path.with_name(CLEARED_NAME).open("a", encoding="utf-8") as handle:
            handle.write("".join(line + "\n" for line in dropped))
        path.write_text("".join(line + "\n" for line in kept), encoding="utf-8")
    return len(dropped)


# -------------------------------------------------------------- the dll


class DllSwap:
    """The installed `bin/server.dll` swapped for the test build, and back.

    The original is moved aside by rename, never copied, so it comes back byte
    for byte. A backup already there means an earlier run never restored it,
    and is kept: it is the real one. A running game keeps the dll it loaded.
    """

    def __init__(self, installed: Path, test_dll: Path) -> None:
        self.installed = installed
        self.test_dll = test_dll
        self.backup = installed.with_name(installed.name + ".aptest-original")

    def check(self) -> str | None:
        """Why the swap cannot go ahead, or None."""
        if not self.test_dll.is_file():
            return (f"{self.test_dll} not found; configure build/game-test with "
                    "-DHL2AP_TEST_BUILD=ON and build it")
        if TEST_DLL_MARKER not in self.test_dll.read_bytes():
            return f"{self.test_dll} is not a test build (HL2AP_TEST_BUILD off)"
        if not self.installed.is_file() and not self.backup.is_file():
            return f"{self.installed} not found; run tools/install_mod.py first"
        return None

    def stale(self, sources: Path) -> list[Path]:
        """Game sources newer than the test dll."""
        built = self.test_dll.stat().st_mtime
        return sorted(p for p in sources.rglob("*") if p.is_file() and p.stat().st_mtime > built)

    def swap_in(self) -> None:
        if self.backup.is_file():
            print(f"Keeping {self.backup.name}, left by a run that did not finish.")
        else:
            os.replace(self.installed, self.backup)
        temp = self.installed.with_name(self.installed.name + ".aptest-tmp")
        shutil.copy2(self.test_dll, temp)
        os.replace(temp, self.installed)
        print(f"Test dll in place: {self.installed}")

    def restore(self) -> None:
        if self.backup.is_file():
            os.replace(self.backup, self.installed)
            print(f"Original dll restored: {self.installed}")


# -------------------------------------------------------------- the harness


class Harness:
    def __init__(self, ctx: Context, groups: dict[str, Group], group: str) -> None:
        self.ctx = ctx
        self.store = ctx.store
        self.groups = groups
        self.bridge = bridge_module.Bridge(self.store)
        self.bridge.reset_cursor()
        self.results_path = self.store / RESULTS_NAME
        self.go_path = self.store / GO_NAME
        self.say_path = self.store / SAY_NAME
        self.store.mkdir(parents=True, exist_ok=True)
        self.say_path.write_text("", encoding="utf-8")
        self.seq = self.last_seq()
        self.items: Counter[str] = Counter()
        self.seen: set[int] = set()
        self.connected = True
        # Re-entrant: a verdict from the game arrives inside the poll and starts
        # the next scenario, which takes the lock again.
        self.lock = threading.RLock()
        self.running = True
        self.group = ""
        self.scenarios: list[Scenario] = []
        self.current = -1
        self.select(group)

    # Talking to the player, in game and here.

    def tell(self, text: str, hud: bool = True) -> None:
        print(text)
        with self.say_path.open("a", encoding="utf-8") as handle:
            for line in text.strip("\n").splitlines():
                handle.write(("hud|" if hud else "con|") + line.strip() + "\n")

    def last_seq(self) -> int:
        """The sequence number the game last saw, so a restarted harness never
        repeats one the game would ignore."""
        if self.go_path.is_file():
            for line in self.go_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("seq="):
                    return int(line[4:] or 0)
        return 0

    # Groups.

    def select(self, name: str) -> bool:
        group = self.groups.get(group_registry.canonical(name, self.groups))
        if group is None:
            self.tell(f"[aptest] No group '{name}'. !groups lists them.")
            return False
        if group.needs_checkdata and self.ctx.checkdata is None:
            self.tell(f"[aptest] '{group.name}' needs checkdata.txt, which is not installed yet.")
            return False
        scenarios = group.build(self.ctx)
        titles = [s.title for s in scenarios]
        if len(set(titles)) != len(titles):
            raise ValueError(f"group {group.name} has duplicate scenario titles")
        with self.lock:
            self.group = group.name
            self.scenarios = scenarios
            self.current = -1
        return True

    def verdicts(self, group: str | None = None) -> dict[str, str]:
        return latest_verdicts(self.results_path, group or self.group, self.groups)

    # The snapshot.

    def publish(self, force: bool = False) -> None:
        s = self.scenario()
        chapters: list[str] = []  # from checkdata once it exists
        options = dict(s.snapshot) if s is not None else {}
        self.bridge.write_snapshot(
            connected=self.connected,
            chapters=[c for c in chapters if s is None or c not in s.closed],
            items=list(self.items.elements()),
            checked=sorted(s.checked) if s is not None else [],
            options=options,
            data_version=self.ctx.data_version,
            slot="aptest:1",
            force=force,
        )

    # Scenarios.

    def scenario(self) -> Scenario | None:
        if 0 <= self.current < len(self.scenarios):
            return self.scenarios[self.current]
        return None

    def start(self, index: int) -> None:
        if not 0 <= index < len(self.scenarios):
            self.tell(f"[aptest] No scenario {index}; there are {len(self.scenarios)}.")
            return
        with self.lock:
            self.current = index
            s = self.scenarios[index]
            self.items = Counter(self.ctx.default_items)
            for name in s.take:
                self.items.pop(name, None)
            for name in s.give:
                self.items[name] += 1
            self.seen = set()
            self.connected = s.connected
            self.publish(force=True)
            # The game loads the map when the sequence number moves, so a redo
            # of the same scenario reloads it too.
            self.seq += 1
            go = [f"seq={self.seq}", f"map={s.map}"]
            go += [f"pos={s.pos}"] if s.pos else []
            go += [f"setup={bridge_module.sanitise(c)}" for c in s.setup]
            temp = self.go_path.with_suffix(".tmp")
            temp.write_text("\n".join(go) + "\n", encoding="utf-8")
            os.replace(temp, self.go_path)
            self.tell(f"[aptest] {self.group} {index}/{len(self.scenarios) - 1}: {s.title}")
            if s.take:
                self.tell(f"[aptest] Without: {', '.join(s.take)}")
            if not s.connected:
                self.tell("[aptest] The client reads as disconnected. !connect to change.")
            self.info()

    def info(self) -> None:
        s = self.scenario()
        if s is None:
            self.tell("[aptest] No scenario running. !next starts the first untested.")
            return
        for number, line in enumerate(reflow(s.steps), 1):
            self.tell(f"{number}. {line}")

    def first_untested(self, after: int = -1) -> int | None:
        verdicts = self.verdicts()
        return next((i for i, s in enumerate(self.scenarios)
                     if i > after and s.title not in verdicts), None)

    def record(self, verdict: str, note: str) -> None:
        s = self.scenario()
        if s is None:
            self.tell("[aptest] No scenario running.")
            return
        sent = ",".join(str(i) for i in sorted(self.seen))
        line = "|".join([time.strftime("%Y-%m-%d %H:%M:%S"), str(self.current), s.title,
                         verdict, note.replace("|", "/"), sent, self.group])
        with self.results_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        self.tell(f"[aptest] Recorded {verdict}.")
        following = self.first_untested(self.current)
        if following is None:
            self.tell("[aptest] That was the last untested scenario in this group.")
            self.status()
        else:
            self.start(following)

    def counts(self, group: str) -> Counter[str]:
        g = self.groups[group]
        if g.needs_checkdata and self.ctx.checkdata is None:
            return Counter()
        verdicts = self.verdicts(group)
        return Counter(verdicts.get(s.title, "untested") for s in g.build(self.ctx))

    def status(self) -> None:
        counts = self.counts(self.group)
        self.tell(f"[aptest] {self.group}: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
        first = self.first_untested()
        if first is not None:
            self.tell(f"[aptest] First untested: {first} {self.scenarios[first].title}")

    def list(self, text: str) -> None:
        verdicts = self.verdicts()
        shown = 0
        for index, s in enumerate(self.scenarios):
            if text.lower() in s.title.lower():
                mark = verdicts.get(s.title, "")
                self.tell(f"{index:4} {('[' + mark + '] ') if mark else ''}{s.title}", hud=False)
                shown += 1
        self.tell(f"[aptest] {shown} listed in the console.")

    def list_groups(self) -> None:
        for name, g in self.groups.items():
            if g.needs_checkdata and self.ctx.checkdata is None:
                summary = "needs checkdata.txt"
            else:
                summary = ", ".join(f"{k} {v}" for k, v in sorted(self.counts(name).items()))
            mark = "*" if name == self.group else " "
            self.tell(f"[aptest] {mark} {name}: {g.summary} ({summary})")

    def clear(self, arg: str) -> None:
        if arg.lower() != "yes":
            self.tell(f"[aptest] This drops every '{self.group}' result "
                      f"({len(self.scenarios)} scenarios). !clear yes to go ahead.")
            return
        count = clear_results(self.results_path, self.group, self.groups)
        self.tell(f"[aptest] Cleared {count} '{self.group}' result(s); "
                  f"they are kept in {CLEARED_NAME}.")
        self.status()

    def command(self, verb: str, arg: str) -> None:
        """One verb, from the game (`!pass`) or typed here (`pass`)."""
        verb = verb.lower()
        with self.lock:
            if verb == "pass":
                self.record("pass", arg)
            elif verb in ("fail", "note"):
                if arg:
                    self.record(verb, arg)
                else:
                    self.tell(f"[aptest] !{verb} needs a note.")
            elif verb == "next":
                if self.current < 0:
                    first = self.first_untested()
                    self.start(0 if first is None else first)
                else:
                    self.start(self.current + 1)
            elif verb == "prev":
                self.start(self.current - 1)
            elif verb == "redo":
                if self.current < 0:
                    self.tell("[aptest] Nothing to redo. !next starts the first untested.")
                else:
                    self.start(self.current)
            elif verb == "go" and arg.isdigit():
                self.start(int(arg))
            elif verb == "info":
                self.info()
            elif verb == "status":
                self.status()
            elif verb == "list":
                self.list(arg)
            elif verb == "groups":
                self.list_groups()
            elif verb == "group" and arg:
                if self.select(arg):
                    self.tell(f"[aptest] Now on group '{self.group}' "
                              f"({len(self.scenarios)} scenarios). !next to begin.")
                    self.status()
            elif verb == "clear":
                self.clear(arg)
            elif verb in ("connect", "disconnect"):
                self.connected = verb == "connect"
                self.publish()
                self.tell(f"[aptest] The client now reads as {verb}ed.")
            elif verb in ("item", "trap") and arg:
                known = FILLER if verb == "item" else TRAPS
                name = next((n for n in known if n.lower() == arg.lower()), None)
                if name is None:
                    name = next((n for n in known if n.lower() == f"{arg} trap".lower()), None)
                if name is None:
                    self.tell(f"[aptest] No {verb} '{arg}'. Try: {', '.join(known)}.")
                    return
                self.bridge.queue_event(verb.upper(), name)
                self.publish()
                self.tell(f"[aptest] {verb} sent: {name}")
            elif verb == "deathlink":
                self.bridge.queue_event("DEATHLINK", "APTest~a test DeathLink")
                self.publish()
                self.tell("[aptest] DeathLink sent.")
            elif verb in ("give", "take") and arg:
                # Chat is not careful about case; the snapshot is.
                known = set(self.ctx.default_items) | set(self.items)
                arg = next((n for n in known if n.lower() == arg.lower()), arg)
                if verb == "give":
                    self.items[arg] += 1
                elif self.items[arg] > 0:
                    self.items[arg] -= 1
                    if not self.items[arg]:
                        del self.items[arg]
                self.publish()
                self.tell(f"[aptest] {verb}: {arg} (now {self.items.get(arg, 0)})")
            else:
                self.tell(HELP)

    # Game to us.

    def judge(self, location_id: int) -> None:
        s = self.scenario()
        if s is not None and location_id in s.expect:
            if location_id not in self.seen:
                self.tell(f"[aptest] Expected check arrived: {location_id}.")
        else:
            self.tell(f"[aptest] Other check: {location_id}")
        self.seen.add(location_id)

    def judge_complete(self, kind: str, key: str) -> None:
        s = self.scenario()
        if s is not None and key in s.expect_complete:
            self.tell(f"[aptest] Expected {kind} arrived: {key}.")
        else:
            self.tell(f"[aptest] Unexpected {kind}: {key}. Was it meant to be sent?")

    def handle(self, event: bridge_module.GameEvent) -> None:
        if event.kind == "CHECK" and event.arg.isdigit():
            self.judge(int(event.arg))
        elif event.kind == "ACK" and event.arg.isdigit():
            self.bridge.acknowledge(int(event.arg))
        elif event.kind in ("COMPLETE", "GOAL"):
            self.judge_complete(event.kind, event.arg)
        elif event.kind in ("DEATH", "CHAT"):
            self.tell(f"[aptest] {event.kind}: " + " | ".join(event.args))
        elif event.kind == "HELLO":
            self.publish(force=True)
        elif event.kind == "APTEST" and event.args:
            verb = event.args[0]
            arg = event.args[1] if len(event.args) > 1 else ""
            print(f"(from game) {verb} {arg}".rstrip())
            self.command(verb, arg.strip())

    def poll(self) -> None:
        while self.running:
            try:
                events = self.bridge.read_events()
            except OSError:
                events = []
            with self.lock:
                for event in events:
                    self.handle(event)
                self.publish()
            time.sleep(0.2)


# -------------------------------------------------------------- cli


def running_harness(lock: Path) -> int | None:
    """The pid of a live harness holding `lock`, or None (stale locks ignored)."""
    try:
        pid = int(lock.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
    if pid == os.getpid():
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return None
    except OSError:
        pass  # alive but not ours, or cannot tell; assume alive
    return pid


def default_mod_dir() -> Path:
    """Where `tools/install_mod.py` put the mod's real files."""
    return mod.proton_game_dir(mod.sourcemod_dir())


def make_context(mod_dir: Path, game_root: Path | None) -> Context:
    store = bridge_module.store_dir(mod_dir)
    ctx = Context(store=store, game_root=game_root)
    checkdata = store / bridge_module.CHECKDATA_NAME
    if checkdata.is_file():
        # Full parsing arrives with the data pipeline (plan Phase 2).
        ctx.checkdata = checkdata
        for line in checkdata.read_text(encoding="utf-8").splitlines():
            if line.startswith("D|"):
                ctx.data_version = line[2:].strip()
    return ctx


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--group", help="the scenario group to run")
    parser.add_argument("--list-groups", action="store_true")
    parser.add_argument("--clear", action="store_true",
                        help="drop the group's results and exit; nothing is launched or swapped")
    parser.add_argument("--mod-dir", type=Path, default=None,
                        help="the installed mod folder (default: where install_mod.py put it)")
    parser.add_argument("--game-root", type=Path, default=os.environ.get("HL2_ROOT"),
                        help="the Half-Life 2 install, for groups that read maps (or HL2_ROOT)")
    parser.add_argument("--test-dll", type=Path, default=TEST_DLL)
    args = parser.parse_args(argv)

    groups = group_registry.discover()
    try:
        mod_dir = args.mod_dir or default_mod_dir()
    except ValueError as exc:
        parser.error(str(exc))
    ctx = make_context(mod_dir, args.game_root)

    if args.list_groups or not args.group:
        for name, g in groups.items():
            print(f"{name:16} {g.summary}" + (" (needs checkdata)" if g.needs_checkdata else ""))
        return 0

    name = group_registry.canonical(args.group, groups)
    if name not in groups:
        parser.error(f"no group {args.group!r}; --list-groups lists them")
    if args.clear:
        count = clear_results(ctx.store / RESULTS_NAME, name, groups)
        print(f"Cleared {count} '{name}' result(s); kept in {CLEARED_NAME}.")
        return 0

    swap = DllSwap(mod_dir / mod.DLL_NAME, args.test_dll)
    problem = swap.check()
    if problem:
        parser.error(problem)
    newer = swap.stale(REPO / "game" / "src")
    if newer:
        print(f"Warning: {len(newer)} game source file(s) are newer than the test dll, "
              f"e.g. {newer[0].relative_to(REPO)}. Rebuild build/game-test.")

    def stop(signum, frame):
        raise KeyboardInterrupt
    for sig in ("SIGTERM", "SIGHUP"):
        if hasattr(signal, sig):
            signal.signal(getattr(signal, sig), stop)

    ctx.store.mkdir(parents=True, exist_ok=True)
    lock = ctx.store / LOCK_NAME
    other = running_harness(lock)
    if other is not None:
        parser.error(f"another harness is already running (pid {other}); stop it first")
    lock.write_text(str(os.getpid()), encoding="utf-8")

    swap.swap_in()
    try:
        return run(ctx, groups, name)
    finally:
        swap.restore()
        lock.unlink(missing_ok=True)


def run(ctx: Context, groups: dict[str, Group], group: str) -> int:
    harness = Harness(ctx, groups, group)
    harness.publish(force=True)
    print("Launch Half-Life 2 Archipelago now (or restart it) so it loads the test dll.")
    print(f"Group '{harness.group}': {len(harness.scenarios)} scenarios.")
    print("Drive it from the game: !next to begin, !pass / !fail <note> / !note <text>.")
    harness.status()
    threading.Thread(target=harness.poll, daemon=True).start()

    while True:
        try:
            line = input().strip()
        except KeyboardInterrupt:
            break
        except EOFError:
            # No terminal: run on, driven from the game, until interrupted.
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                break
        verb, _, arg = line.partition(" ")
        if verb in ("quit", "exit"):
            break
        if verb:
            harness.command(verb, arg.strip())
    harness.running = False
    # A game started later must not load a scenario nobody is running.
    harness.go_path.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

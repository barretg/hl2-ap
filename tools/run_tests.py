"""Run the tests: the host suite and the world tests always, Archipelago's
general tests only for a release.

The host suite is this repo's pytest (`tests/`). Extra arguments go to it, so
`-m bridge` or `-k name` pick a subset as with plain pytest.

The world tests (`apworld/half_life_2/test/`) import Archipelago, so they run
in its source checkout (`../Archipelago-src`, or `--ap`), with the world linked
into its `worlds/` (see the command printed when it is not). Without a usable
checkout they are skipped, except for a release.

`--release` adds Archipelago's general tests, which load every world and take
minutes, so they are for a release, not every change.

Usage:
    python tools/run_tests.py [pytest args]
    python tools/run_tests.py --release   # adds the general tests
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORLD = REPO / "apworld" / "half_life_2"
DEFAULT_AP = REPO.parent / "Archipelago-src"

# Fails on worlds other than ours that do not load in the checkout; our own
# world failing to load fails its world tests first.
KNOWN_UNRELATED = ["test/general/test_implemented.py::TestImplemented::test_no_failed_world_loads"]


def run(command: list[str], cwd: Path) -> bool:
    print(f"\n== {' '.join(command)}  (in {cwd})", flush=True)
    return subprocess.run(command, cwd=cwd).returncode == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--release", action="store_true",
                        help="also run Archipelago's general tests (slow)")
    parser.add_argument("--ap", type=Path, default=DEFAULT_AP,
                        help="the Archipelago source checkout (default: ../Archipelago-src)")
    args, pytest_args = parser.parse_known_args(argv)

    results = {"host": run([sys.executable, "-m", "pytest", "-q", *pytest_args], REPO)}

    python = args.ap / ".venv" / "bin" / "python"
    link = args.ap / "worlds" / WORLD.name
    problem = None
    if not python.exists():
        problem = f"no Python venv at {python}"
    elif link.resolve() != WORLD.resolve():
        problem = f"{link} is not this world. Link it with:\n    ln -s {WORLD} {link}"
    if problem is not None:
        print(f"\n{problem}")
        if args.release:
            return 1
        print("world tests skipped")
    else:
        results["world"] = run([str(python), "-m", "pytest", "-q", f"worlds/{WORLD.name}"],
                               args.ap)
        if args.release:
            deselect = [arg for test in KNOWN_UNRELATED for arg in ("--deselect", test)]
            results["general"] = run(
                [str(python), "-m", "pytest", "-q", "test/general", *deselect], args.ap)

    print("\n" + "  ".join(f"{name}: {'ok' if ok else 'FAILED'}" for name, ok in results.items()))
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())

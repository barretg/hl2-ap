"""Build everything: data, SDK patches, both DLL sets and the apworld.

In order:
  1. campaign data   tools/build_campaign_data.py  (reads the HL2 install)
  2. check data      tools/gen_checkdata.py
  3. voice lines     tools/gen_voice_lines.py      (reads the HL2 install)
     hub picture     tools/gen_chapter_image.py    (from assets/ap_logo.png)
  4. SDK patches     tools/sdk_patches.py          (from ../source-sdk-2013)
  5. DLLs            build/game (release) and build/game-test (scenario
                     harness), each configured with CMake on first use
  6. apworld         tools/build_apworld.py        (bundles build/game's DLLs)
  7. worlds copy     the apworld into Archipelago's worlds folder
                     (`--worlds`, default /games/Archipelago/worlds on Linux;
                     skipped with `--no-install`)

Does not install the mod: run `python tools/install_mod.py` afterwards for that.

Usage:
    python build.py [--game "<Half-Life 2 folder>"] [--skip-data] [--only release|test]
                    [--worlds "<Archipelago worlds folder>" | --no-install]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent
TOOLS = REPO / "tools"
SDK = REPO.parent / "source-sdk-2013"
TOOLCHAIN = REPO / "game" / "toolchain-clangcl-x86.cmake"
DLL_BUILDS = {"release": (REPO / "build" / "game", "OFF"),
              "test": (REPO / "build" / "game-test", "ON")}
APWORLD = REPO / "build" / "half_life_2.apworld"
DEFAULT_WORLDS = Path("/games/Archipelago/worlds") if sys.platform.startswith("linux") else None


def run(label: str, command: list[str]) -> None:
    print(f"== {label}", flush=True)
    started = time.monotonic()
    result = subprocess.run(command, cwd=REPO)
    if result.returncode != 0:
        print(f"!! {label} failed (exit {result.returncode})", file=sys.stderr)
        sys.exit(result.returncode)
    print(f"   {label}: {time.monotonic() - started:.1f}s", flush=True)


def tool(name: str, *args: str) -> list[str]:
    return [sys.executable, str(TOOLS / name), *args]


def build_dlls(which: str) -> None:
    out, test = DLL_BUILDS[which]
    if not (out / "CMakeCache.txt").is_file():
        run(f"configure {which} DLLs",
            ["cmake", "-S", "game", "-B", str(out), "-G", "Ninja",
             f"-DCMAKE_TOOLCHAIN_FILE={TOOLCHAIN}", f"-DSDK_DIR={SDK}",
             f"-DHL2AP_TEST_BUILD={test}"])
    run(f"build {which} DLLs", ["cmake", "--build", str(out)])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--game", type=Path, help="the Half-Life 2 install folder")
    parser.add_argument("--skip-data", action="store_true",
                        help="skip steps 1 to 3 (no install needed)")
    parser.add_argument("--only", choices=sorted(DLL_BUILDS),
                        help="build one DLL set; the apworld is packaged only with release")
    parser.add_argument("--worlds", type=Path, default=DEFAULT_WORLDS,
                        help=f"Archipelago worlds folder to copy the apworld into "
                             f"(default: {DEFAULT_WORLDS or 'none off Linux'})")
    parser.add_argument("--no-install", action="store_true",
                        help="leave the apworld in build/ only")
    args = parser.parse_args(argv)

    for program in ("cmake", "ninja"):
        if shutil.which(program) is None:
            print(f"{program} not found on PATH", file=sys.stderr)
            return 2
    install = args.only != "test" and not args.no_install
    if install and (args.worlds is None or not args.worlds.is_dir()):
        print(f"Archipelago worlds folder not found: {args.worlds} "
              f"(pass --worlds <folder> or --no-install)", file=sys.stderr)
        return 2
    if not SDK.is_dir():
        print(f"SDK checkout not found at {SDK} (see game/README.md)", file=sys.stderr)
        return 2

    game = ["--game", str(args.game)] if args.game else []
    if not args.skip_data:
        run("campaign data", tool("build_campaign_data.py", *game))
        run("check data", tool("gen_checkdata.py"))
        run("voice lines", tool("gen_voice_lines.py", *game))
        run("hub picture", tool("gen_chapter_image.py"))
    run("SDK patches", tool("sdk_patches.py", "--sdk", str(SDK)))
    for which in ([args.only] if args.only else ["release", "test"]):
        build_dlls(which)
    if args.only != "test":
        run("apworld", tool("build_apworld.py"))
    if install:
        print(f"== worlds copy -> {args.worlds}", flush=True)
        shutil.copy2(APWORLD, args.worlds / APWORLD.name)
    print("== done. Install the mod with: python tools/install_mod.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())

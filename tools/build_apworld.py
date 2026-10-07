"""Package the world folder as a distributable `.apworld` in `build/`.

An .apworld is a zip whose single top-level folder matches the zip's stem,
which is the layout of `apworld/half_life_2`.

A release has to carry the server and client dlls, which are build artifacts:
they are read from `build/game/` (the CMake output) and written into the zip
at `half_life_2/mod/files/bin/`, so nothing built ever lands in the source
tree. Packaging a checkout that never built them gives an apworld that
installs and does not run, so they are required unless `--allow-no-dll`.

Nothing is installed anywhere unless `--install <worlds dir>` is given.

Usage:
    python tools/build_apworld.py
    python tools/build_apworld.py --allow-no-dll   # a dev build, mod won't run
    python tools/build_apworld.py --install "F:/Archipelago/custom_worlds"
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path

# apworld container format version, as understood by the Archipelago loader.
MANIFEST_VERSION = 8
MANIFEST_COMPATIBLE_VERSION = 5

REPO_ROOT = Path(__file__).resolve().parent.parent
WORLD_DIR = REPO_ROOT / "apworld" / "half_life_2"
BUILD_DIR = REPO_ROOT / "build"
DLL_BUILD_DIR = BUILD_DIR / "game"

# `mod` owns where the dlls live inside the package and the mod folder.
sys.path.insert(0, str(WORLD_DIR))

import mod  # noqa: E402

# `{path inside the world package: built file}`: the dlls, and the hub map
# compiled from `maps/alpha_hub.vmf`.
HUB_MAP_BUILT = REPO_ROOT / mod.HUB_MAP_TARGET
BUILT: dict[str, Path] = {
    f"mod/{mod.HUB_MAP_PACKAGED}": HUB_MAP_BUILT,
    f"mod/files/{mod.DLL_NAME}": DLL_BUILD_DIR / Path(mod.DLL_NAME).name,
    f"mod/files/{mod.CLIENT_DLL_NAME}": DLL_BUILD_DIR / Path(mod.CLIENT_DLL_NAME).name,
}

EXCLUDE_DIRS = {"__pycache__", ".pytest_cache", "test"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}


def iter_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in EXCLUDE_DIRS for part in path.relative_to(root).parts):
            continue
        if path.suffix in EXCLUDE_SUFFIXES:
            continue
        yield path


def packaged_manifest() -> str:
    """The manifest plus the fields only a zipped apworld needs."""
    manifest = json.loads((WORLD_DIR / "archipelago.json").read_text(encoding="utf-8"))
    manifest["version"] = MANIFEST_VERSION
    manifest["compatible_version"] = MANIFEST_COMPATIBLE_VERSION
    return json.dumps(manifest, indent=1) + "\n"


def missing_dlls() -> list[Path]:
    return [built for built in BUILT.values() if not built.is_file()]


def build(out_dir: Path, allow_no_dll: bool = False) -> Path:
    """Zip the world up. Checked before the zip opens, so a refused build
    leaves the last one alone rather than a truncated file."""
    missing = missing_dlls()
    if missing and not allow_no_dll:
        raise SystemExit(
            "missing " + ", ".join(str(p) for p in missing) + ": this would package an "
            "apworld that installs but cannot run.\nBuild them (see game/README.md), "
            "or pass --allow-no-dll for a development build."
        )
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{WORLD_DIR.name}.apworld"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in iter_files(WORLD_DIR):
            relative = path.relative_to(WORLD_DIR).as_posix()
            if relative in BUILT:
                continue  # a stale copy in the tree never wins over the build
            arcname = f"{WORLD_DIR.name}/{relative}"
            if relative == "archipelago.json":
                archive.writestr(arcname, packaged_manifest())
            else:
                archive.write(path, arcname)
        for relative, built in BUILT.items():
            if built.is_file():
                archive.write(built, f"{WORLD_DIR.name}/{relative}")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=BUILD_DIR)
    parser.add_argument("--install", type=Path, default=None,
                        help="also copy the result into this Archipelago worlds folder")
    parser.add_argument("--allow-no-dll", action="store_true",
                        help="package without the dlls; the mod will not run. Not for a release")
    args = parser.parse_args(argv)

    target = build(args.out, allow_no_dll=args.allow_no_dll)
    print(f"built {target} ({target.stat().st_size / 1024:.0f} KiB)")
    if missing_dlls():
        print("warning: dlls missing from this build; it installs but will not run")
    if args.install:
        if not args.install.is_dir():
            raise SystemExit(f"{args.install} does not exist")
        destination = args.install / target.name
        shutil.copy2(target, destination)
        print(f"installed to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

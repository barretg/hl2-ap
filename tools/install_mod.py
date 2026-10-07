"""Install the `hl2ap` mod folder as a Steam sourcemod.

A thin CLI over the world's `mod` package, which is the same code the client's
`/install` command will run. Useful when working on the game side without going
through the Archipelago Launcher.

The mod goes to Steam's sourcemods folder (found from Steam's own settings), so
the Half-Life 2 install is never written to, and Steam lists "Half-Life 2
Archipelago" in the library after a Steam restart. On Linux the files go where
Proton resolves Steam's launch path (see `mod.proton_game_dir`).

The server dll comes from the package if it bundles one, otherwise from a local
build (`build/game/server.dll` by default, or `--dll`).

Usage:
    python tools/install_mod.py
    python tools/install_mod.py --uninstall
    python tools/install_mod.py --sourcemods /path/to/steamapps/sourcemods
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "apworld" / "half_life_2"))

import mod  # noqa: E402

DEFAULT_DLL = REPO_ROOT / "build" / "game" / "server.dll"
DEFAULT_CLIENT_DLL = REPO_ROOT / "build" / "game" / "client.dll"
DEFAULT_HUB_MAP = REPO_ROOT / mod.HUB_MAP_TARGET


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sourcemods", type=Path, default=None,
                        help="Steam sourcemods folder (default: from Steam's settings)")
    parser.add_argument("--dll", type=Path, default=None,
                        help=f"server dll to install (default: bundled, else {DEFAULT_DLL})")
    parser.add_argument("--client-dll", type=Path, default=None,
                        help=f"client dll to install (default: bundled, else {DEFAULT_CLIENT_DLL})")
    parser.add_argument("--hl2", type=Path, default=None,
                        help="retail Half-Life 2 folder, read for its localization "
                             "(default: from Steam's library records)")
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args(argv)

    try:
        target = mod.sourcemod_dir(args.sourcemods)

        if args.uninstall:
            removed = mod.uninstall_sourcemod(target)
            print(f"removed {removed} files from {target}")
            print("your saves and configs there, if any, were kept")
            return 0

        dll_path = args.dll
        if dll_path is None and mod.read_mod_file(f"files/{mod.DLL_NAME}") is None:
            dll_path = DEFAULT_DLL if DEFAULT_DLL.is_file() else None
        dll = dll_path.read_bytes() if dll_path else None
        client_path = args.client_dll
        if client_path is None and mod.read_mod_file(f"files/{mod.CLIENT_DLL_NAME}") is None:
            client_path = DEFAULT_CLIENT_DLL if DEFAULT_CLIENT_DLL.is_file() else None
        client = client_path.read_bytes() if client_path else None
        hub_map = None
        if mod.read_mod_file(mod.HUB_MAP_PACKAGED) is None:
            if not DEFAULT_HUB_MAP.is_file():
                raise SystemExit(f"{DEFAULT_HUB_MAP} is missing; compile maps/alpha_hub.vmf")
            hub_map = DEFAULT_HUB_MAP.read_bytes()
        hl2_dir = args.hl2 or mod.hl2_install_dir()
        game_dir, written, has_dll = mod.install_sourcemod(target, dll=dll, client_dll=client,
                                                           hl2_dir=hl2_dir, hub_map=hub_map)
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc))

    print(f"wrote {written} files into {game_dir}")
    if game_dir != target:
        print(f"Steam entry stub: {target / 'gameinfo.txt'} (files live in the folder above,")
        print("  where Proton resolves Steam's path; see mod.proton_game_dir)")
    if dll_path:
        print(f"server dll: {dll_path}")
    if client_path:
        print(f"client dll: {client_path}")
    if hl2_dir is None or not mod.localization_files(hl2_dir):
        print("warning: Half-Life 2's localization was not found, so menus will show\n"
              "  #HL2_* tokens; pass --hl2 <Half-Life 2 folder>")
    if not has_dll:
        print(
            f"\nNo server dll was available, so the mod cannot run.\n"
            f"Build it from game/ (see game/README.md) and run this again.")
        return 0

    print("\nRestart Steam once; \"Half-Life 2 Archipelago\" then appears in the library.")
    if sys.platform != "win32":
        print("On Linux, set that entry's Properties > Compatibility to a Proton version\n"
              "(Steam does not inherit Half-Life 2's setting; see game/README.md).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

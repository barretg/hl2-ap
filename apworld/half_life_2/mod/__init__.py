"""The `hl2ap` game folder, and installing it.

The game side of this project is a server dll built from Valve's Source SDK 2013
(singleplayer), shipped as a Steam sourcemod so the player's Half-Life 2 install
is never written to. Steam lists every folder in `steamapps/sourcemods` that has
a `gameinfo.txt` as its own library entry, and launches it with the retail
`hl2.exe` (gameinfo's `SteamAppId` 220). The engine resolves gameinfo search
paths against `hl2.exe`'s folder, so the retail content mounts as usual, while
`|gameinfo_path|` (our dll, saves, the bridge) is the sourcemod folder.

    <Steam>/steamapps/sourcemods/
      hl2ap/
        gameinfo.txt    the mod manifest and search paths
        bin/server.dll  the server dll built from game/
        archipelago/    the file bridge

A fallback installs the same folder beside `hl2_complete` instead, started with
`-game hl2ap`; it gets no library entry.

Bundled files live inside the world package so a zipped `.apworld` carries
everything needed. Every read goes through `pkgutil.get_data`, which works the
same for a folder world and a zipped one.

The client's `/install` command (later) and `tools/install_mod.py` both call in
here, so there is one implementation of what installing means.
"""

from __future__ import annotations

import os
import pkgutil
import re
import sys
from pathlib import Path

# The mod folder's name, which is also what the player passes to `-game`.
MOD_DIR = "hl2ap"

# The retail game folder our gameinfo.txt derives from. Its presence is how an
# install path is recognised.
BASE_GAME_DIR = "hl2_complete"

# Where the bridge and the generated data live, under the mod folder.
STORE_SUBDIR = "archipelago"

# The server dll, relative to the mod folder. Built from `game/`, not committed:
# packaging picks it up, so a released `.apworld` installs a working mod and a
# development checkout installs everything but the dll and says so.
DLL_NAME = "bin/server.dll"

# Our client dll, if we ever ship one (plan: client option B). Without it the
# engine falls through to hl2_complete/bin/client.dll.
CLIENT_DLL_NAME = "bin/client.dll"

# Files bundled in this package, as (path inside the package, path inside the
# mod folder). The dlls are looked up separately because they may be absent.
MOD_FILES = (
    ("files/gameinfo.txt", "gameinfo.txt"),
)

# Files installed once and then left alone, because the player is expected to
# edit them. Empty until we ship configs.
PLAYER_OWNED: frozenset[str] = frozenset()


def read_mod_file(relative_path: str) -> bytes | None:
    """A bundled file's bytes, or None if it is not in this package."""
    try:
        return pkgutil.get_data(__name__, relative_path)
    except (FileNotFoundError, OSError):
        return None


def sourcemods_dir() -> Path | None:
    """Steam's sourcemods folder, as Steam itself records it, or None.

    Windows keeps it in the registry; Linux Steam keeps the same key in
    `~/.steam/registry.vdf`. Either may hold a path with mixed separators.
    """
    raw = None
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
                raw, _ = winreg.QueryValueEx(key, "SourceModInstallPath")
        except OSError:
            raw = None
    else:
        vdf = Path.home() / ".steam" / "registry.vdf"
        try:
            match = re.search(r'"SourceModInstallPath"\s+"([^"]+)"', vdf.read_text(errors="replace"))
        except OSError:
            match = None
        if match:
            raw = match.group(1).replace("\\\\", "/").replace("\\", "/")
        else:
            fallback = Path.home() / ".local" / "share" / "Steam" / "steamapps" / "sourcemods"
            raw = str(fallback) if fallback.is_dir() else None
    return Path(raw) if raw else None


def sourcemod_dir(sourcemods: str | os.PathLike[str] | None = None) -> Path:
    """The mod folder inside Steam's sourcemods (the default install)."""
    root = Path(sourcemods) if sourcemods else sourcemods_dir()
    if root is None:
        raise ValueError("could not find Steam's sourcemods folder; pass it explicitly")
    return root / MOD_DIR


def resolve_game_root(game_dir: str | os.PathLike[str]) -> Path:
    """Accept the install root, `hl2_complete`, or the `hl2ap` folder itself."""
    root = Path(game_dir)
    if (root / BASE_GAME_DIR).is_dir():
        return root
    if root.name.lower() in (BASE_GAME_DIR, MOD_DIR) and (root.parent / BASE_GAME_DIR).is_dir():
        return root.parent
    raise ValueError(
        f"{root} does not look like a Half-Life 2 installation (no {BASE_GAME_DIR} folder)")


def game_mod_dir(game_dir: str | os.PathLike[str]) -> Path:
    """The mod folder beside `hl2_complete` (the fallback install)."""
    return resolve_game_root(game_dir) / MOD_DIR


def _write(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def install(target_root: Path, dll: bytes | None = None,
            client_dll: bytes | None = None) -> tuple[int, bool]:
    """Create the mod folder `target_root` and fill it in.

    `dll`/`client_dll` override what the package bundles (a development build).
    Returns (files written, whether a server dll was among them). False is not
    a failure: it means no dll was available, and the caller should say where
    one comes from.
    """
    written = 0
    for source, relative in MOD_FILES:
        data = read_mod_file(source)
        if data is None:
            raise FileNotFoundError(f"{__name__}/{source} is missing from the world package")
        target = target_root / relative
        if relative in PLAYER_OWNED and target.exists():
            continue  # yours now; see PLAYER_OWNED
        _write(target, data)
        written += 1
    (target_root / STORE_SUBDIR).mkdir(exist_ok=True)

    if dll is None:
        dll = read_mod_file(f"files/{DLL_NAME}")
    if dll is not None:
        _write(target_root / DLL_NAME, dll)
        written += 1

    # The client has to match the server it was built with, so an install
    # without one also takes away one an earlier install left.
    if client_dll is None:
        client_dll = read_mod_file(f"files/{CLIENT_DLL_NAME}")
    target = target_root / CLIENT_DLL_NAME
    if client_dll is not None:
        _write(target, client_dll)
        written += 1
    elif target.is_file():
        target.unlink()

    return written, dll is not None


def uninstall(target_root: Path) -> int:
    """Remove the files this mod owns. Returns the number of files removed.

    Swept by ownership, not by deleting the folder: the player's saves and
    configs live in `hl2ap/` too and survive, as does the folder if anything is
    left in it.
    """
    return sweep(Path(target_root))


def sweep(directory: Path) -> int:
    """Delete the files this mod owns, then any directory that emptied."""
    if not directory.is_dir():
        return 0

    owned = {relative for _, relative in MOD_FILES} | {DLL_NAME, CLIENT_DLL_NAME}
    removed = 0
    for relative in sorted(owned):
        path = directory / relative
        if path.is_file():
            path.unlink()
            removed += 1

    # The bridge directory, live session files and all.
    store = directory / STORE_SUBDIR
    if store.is_dir():
        for path in sorted(store.iterdir()):
            if path.is_file():
                path.unlink()
                removed += 1

    for path in sorted(directory.rglob("*"), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    if not any(directory.iterdir()):
        directory.rmdir()

    return removed


def is_installed(target_root: Path) -> bool:
    """Is there a mod folder with a dll in it?"""
    root = Path(target_root)
    return (root / "gameinfo.txt").is_file() and (root / DLL_NAME).is_file()

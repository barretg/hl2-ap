"""The `hl2ap` sourcemod folder, and installing it.

The game side of this project is a server dll built from Valve's Source SDK 2013
(singleplayer), shipped as a Steam sourcemod so the player's Half-Life 2 install
is never written to. Steam lists every folder in `steamapps/sourcemods` that has
a `gameinfo.txt` as its own library entry ("Half-Life 2 Archipelago", from
gameinfo's `game` key), and launches it with the retail `hl2.exe`.

The mod is a plain HL2 mod named `hl2ap`. The anniversary binaries special-case
the `hl2_complete` game, but they test the literal `-game` command-line value,
which for a sourcemod is always a full path, so no mod folder can get that
behaviour; and its per-campaign content switching lives in Valve's private
hl2_complete server code. So we mount only HL2's content, as retail `hl2` does.

    <Steam>/steamapps/sourcemods/
      hl2ap/
        gameinfo.txt    the mod manifest and search paths
        bin/server.dll  the server dll built from game/
        archipelago/    the file bridge

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

# The mod folder's name.
MOD_DIR = "hl2ap"

# Where the bridge and the generated data live, under the mod folder.
STORE_SUBDIR = "archipelago"

# The server dll, relative to the mod folder. Built from `game/`, not committed:
# packaging picks it up, so a released `.apworld` installs a working mod and a
# development checkout installs everything but the dll and says so.
DLL_NAME = "bin/server.dll"

# Our client dll, built from the same SDK as the server (single-player chat;
# our HUD later). Without it the engine falls through to hl2/bin/client.dll.
CLIENT_DLL_NAME = "bin/client.dll"

# Files bundled in this package, as (path inside the package, path inside the
# mod folder). The dlls are looked up separately because they may be absent.
MOD_FILES = (
    ("files/gameinfo.txt", "gameinfo.txt"),
    # HL2 ships no chat layout; see the file's header.
    ("files/resource/ui/basechat.res", "resource/ui/basechat.res"),
    # Generated from campaign.json by tools/gen_checkdata.py.
    ("files/archipelago/checkdata.txt", "archipelago/checkdata.txt"),
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


# Retail HL2's localization (`hl2/resource/hl2_<language>.txt`, UTF-16), copied
# in as `resource/hl2ap_<language>.txt`: the engine loads only
# `resource/<mod folder>_<language>.txt` for a mod, so without these every
# `#HL2_*` token (chapter titles, weapon names) shows raw. Copied from the
# player's own install at install time, never shipped.
LOCALIZATION_SOURCE = re.compile(r"hl2_([a-z]+)\.txt")
LOCALIZATION_TARGET = "resource/" + MOD_DIR + "_{}.txt"


# GameUI's New Game dialog looks chapter titles up as `#<mod>_Chapter<N>_Title`,
# with <mod> our folder name, so each `HL2_Chapter...` key is repeated under it.
CHAPTER_KEY = re.compile(r'^([ \t]*)"HL2_(Chapter\w+)"([^\r\n]*)', re.IGNORECASE | re.MULTILINE)


def localization_text(source: Path) -> bytes:
    """A retail `hl2_<language>.txt` with chapter keys added under our mod name.

    Valve's files are UTF-16 with a BOM; one that does not decode is copied as is.
    """
    raw = source.read_bytes()
    if not raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw
    try:
        text = raw.decode("utf-16")
    except UnicodeDecodeError:
        return raw
    added = CHAPTER_KEY.sub(lambda m: f'{m.group(0)}\r\n{m.group(1)}"{MOD_DIR}_{m.group(2)}"'
                            f'{m.group(3)}', text)
    return added.encode("utf-16")


def hl2_install_dir(library: Path | None = None) -> Path | None:
    """The retail Half-Life 2 folder, or None if Steam's records do not say."""
    library = library or steam_library_of()
    if library is None:
        return None
    path = library / "steamapps" / "common" / "Half-Life 2"
    return path if (path / "hl2").is_dir() else None


def localization_files(hl2_dir: Path) -> list[tuple[Path, str]]:
    """(retail file, path inside the mod folder) for each HL2 language."""
    resource = Path(hl2_dir) / "hl2" / "resource"
    if not resource.is_dir():
        return []
    found = []
    for path in sorted(resource.iterdir()):
        match = LOCALIZATION_SOURCE.fullmatch(path.name.lower())
        if match and path.is_file():
            found.append((path, LOCALIZATION_TARGET.format(match.group(1))))
    return found


# The hub, until the project ships its own: a menu background from the
# player's install, copied in under a name of its own. The engine refuses to
# save on a map named background*, and hub warp points are saves. Matches
# `HUB_MAP`/`HUB_SOURCE_MAP` in tools/campaigns.
HUB_MAP_SOURCE = "hl2/maps/background05.bsp"
HUB_MAP_TARGET = "maps/temp_hub.bsp"


# Half-Life 2's Steam app id: the library that holds it is the drive Proton
# starts hl2.exe on.
HL2_APP_ID = "220"


# Retail HL2's HUD layout, copied in as `scripts/hudlayout.res` with two changes.
# HL2 ships the chat panel (`HudChat`) 4x4 pixels in the corner, so chat and
# `messagemode` work but cannot be seen, and chat is where the game side talks
# to the player and where `!` commands are typed. The block is replaced with
# HL2DM's geometry. And the numbered menu (`HudMenu`, the `!menu` menu) asks
# for fonts and colours HL2's scheme never defines (`MenuTextFont`,
# `MenuColor`...), so it drew nothing; its block names HL2's own instead.
# Every other element stays as the player's install has it.
HUDLAYOUT_SOURCE = "hl2/scripts/hudlayout.res"
HUDLAYOUT_TARGET = "scripts/hudlayout.res"
HUDCHAT_BLOCK = re.compile(r'(?ms)^([ \t]*)HudChat\s*\{.*?^[ \t]*\}')
HUDCHAT_LAYOUT = (
    '{i}HudChat\r\n{i}{{\r\n'
    '{i}\t"ControlName"\t"EditablePanel"\r\n'
    '{i}\t"fieldName"\t"HudChat"\r\n'
    '{i}\t"visible"\t"0"\r\n'
    '{i}\t"enabled"\t"1"\r\n'
    '{i}\t"xpos"\t"10"\r\n'
    '{i}\t"ypos"\t"275"\r\n'
    '{i}\t"wide"\t"320"\r\n'
    '{i}\t"tall"\t"120"\r\n'
    '{i}\t"PaintBackgroundType"\t"2"\r\n'
    '{i}}}'
)


HUDMENU_BLOCK = re.compile(r'(?ms)^([ \t]*)HudMenu\s*\{.*?^[ \t]*\}')
HUDMENU_LAYOUT = (
    '{i}HudMenu\r\n{i}{{\r\n'
    '{i}\t"fieldName"\t"HudMenu"\r\n'
    '{i}\t"visible"\t"1"\r\n'
    '{i}\t"enabled"\t"1"\r\n'
    '{i}\t"wide"\t"640"\r\n'
    '{i}\t"tall"\t"480"\r\n'
    '{i}\t"TextFont"\t"HudHintTextSmall"\r\n'
    '{i}\t"ItemFont"\t"HudHintTextSmall"\r\n'
    '{i}\t"ItemFontPulsing"\t"HudHintTextLarge"\r\n'
    '{i}\t"MenuColor"\t"BrightFg"\r\n'
    '{i}\t"MenuItemColor"\t"BrightFg"\r\n'
    '{i}\t"MenuBoxColor"\t"SelectionBoxBg"\r\n'
    '{i}}}'
)


def hudlayout_text(hl2_dir: Path) -> bytes | None:
    """The player's HL2 HUD layout with a visible chat panel, or None when the
    install has no layout file or no `HudChat` block to replace."""
    source = Path(hl2_dir) / HUDLAYOUT_SOURCE
    if not source.is_file():
        return None
    text = source.read_bytes().decode("utf-8", errors="surrogateescape")
    patched, count = HUDCHAT_BLOCK.subn(lambda m: HUDCHAT_LAYOUT.format(i=m.group(1)), text, count=1)
    if count == 0:
        return None
    patched = HUDMENU_BLOCK.sub(lambda m: HUDMENU_LAYOUT.format(i=m.group(1)), patched, count=1)
    return patched.encode("utf-8", errors="surrogateescape")


def steam_library_of(app_id: str = HL2_APP_ID) -> Path | None:
    """The Steam library folder that has `app_id` installed, or None (Linux)."""
    vdf = Path.home() / ".local" / "share" / "Steam" / "steamapps" / "libraryfolders.vdf"
    try:
        text = vdf.read_text(errors="replace")
    except OSError:
        return None
    # Each library is a block with a "path" followed by its "apps" block.
    for match in re.finditer(r'"path"\s+"([^"]+)"(.*?)(?="path"|\Z)', text, re.S):
        apps = re.search(r'"apps"\s*\{([^}]*)\}', match.group(2))
        if apps and re.search(rf'"{re.escape(app_id)}"\s+"', apps.group(1)):
            return Path(match.group(1))
    return None


def proton_link_path(target_root: Path, library: Path | None = None) -> Path | None:
    """Where the Proton path link for a sourcemod goes, or None when not needed.

    Linux Steam launches a sourcemod as `hl2.exe -game <linux path>`. Under
    Proton the engine reads a path starting with `/` as relative to the
    current drive, which is the library holding HL2 (S: here), so it looks in
    `<library>/home/...` and reports gameinfo.txt missing. A link at that spot,
    pointing at the real folder, makes the library entry work. Only a link is
    added to the library; nothing in the HL2 install is touched.
    """
    if sys.platform == "win32":
        return None
    library = library or steam_library_of()
    if library is None:
        return None
    target_root = Path(target_root).absolute()
    link = library / target_root.relative_to(target_root.anchor)
    return None if link == target_root else link


def proton_game_dir(steam_dir: Path, library: Path | None = None) -> Path:
    """Where the mod's files really live for a sourcemod install.

    On Windows, the sourcemod folder itself. Under Proton (see
    `proton_link_path`), the spot the engine actually resolves Steam's path to,
    in HL2's library; the sourcemod folder then holds only the gameinfo.txt
    stub Steam needs to list the mod. A symlink there instead (what the
    abandoned HL:Source attempt did) makes Wine abort with a double free in its
    own path code as soon as the engine searches for dlls through it.
    """
    return proton_link_path(steam_dir, library) or Path(steam_dir)


def install_sourcemod(steam_dir: Path, dll: bytes | None = None,
                      client_dll: bytes | None = None,
                      library: Path | None = None,
                      hl2_dir: Path | None = None) -> tuple[Path, int, bool]:
    """Install as a Steam sourcemod. Returns (game folder, files written, has dll)."""
    steam_dir = Path(steam_dir)
    game_dir = proton_game_dir(steam_dir, library)
    if game_dir.is_symlink():
        game_dir.unlink()  # left by an earlier install that used a link
    proton = game_dir != steam_dir
    written, has_dll = install(game_dir, dll=dll, client_dll=client_dll, absolute_paths=proton,
                               hl2_dir=hl2_dir or hl2_install_dir(library))
    if proton:
        # The stub Steam lists. Only gameinfo.txt: anything else here would be
        # a second copy the engine never reads.
        sweep(steam_dir)
        _write(steam_dir / "gameinfo.txt", gameinfo_text(wine_path(game_dir)))
        written += 1
    return game_dir, written, has_dll


def uninstall_sourcemod(steam_dir: Path, library: Path | None = None) -> int:
    """Undo `install_sourcemod`. Returns the number of files removed."""
    steam_dir = Path(steam_dir)
    game_dir = proton_game_dir(steam_dir, library)
    removed = clear_warp_saves(game_dir) if game_dir.is_dir() else 0
    if game_dir != steam_dir:
        if game_dir.is_symlink():
            game_dir.unlink()
        else:
            removed += sweep(game_dir)
        root = (library or steam_library_of()).absolute()
        parent = game_dir.parent
        while parent != root and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
    return removed + sweep(steam_dir)


def _write(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)


def wine_path(path: Path) -> str:
    """`path` as Proton's Z: drive sees it (Z: is the Linux root)."""
    return "Z:" + Path(path).absolute().as_posix().rstrip("/") + "/"


def gameinfo_text(absolute_root: str | None = None) -> bytes:
    """The bundled gameinfo.txt, with `|gameinfo_path|` made absolute if asked.

    Under Proton, Steam launches a sourcemod with a drive-relative path
    (`\\home\\...`), and search paths built from it make Wine abort inside
    its own path code as soon as client.dll loads. The same paths written
    out absolute (`Z:/...`) work, so a Linux install writes them that way.
    """
    data = read_mod_file("files/gameinfo.txt")
    if data is None:
        raise FileNotFoundError(f"{__name__}/files/gameinfo.txt is missing from the world package")
    if absolute_root:
        data = data.replace(b"|gameinfo_path|", absolute_root.encode())
    return data


def install(target_root: Path, dll: bytes | None = None,
            client_dll: bytes | None = None,
            absolute_paths: bool = False,
            hl2_dir: Path | None = None) -> tuple[int, bool]:
    """Create the mod folder `target_root` and fill it in.

    `dll`/`client_dll` override what the package bundles (a development build).
    Returns (files written, whether a server dll was among them). False is not
    a failure: it means no dll was available, and the caller should say where
    one comes from.
    """
    written = 0
    for source, relative in MOD_FILES:
        if source == "files/gameinfo.txt":
            data = gameinfo_text(wine_path(target_root) if absolute_paths else None)
        else:
            data = read_mod_file(source)
        if data is None:
            raise FileNotFoundError(f"{__name__}/{source} is missing from the world package")
        target = target_root / relative
        if relative in PLAYER_OWNED and target.exists():
            continue  # yours now; see PLAYER_OWNED
        _write(target, data)
        written += 1
    (target_root / STORE_SUBDIR).mkdir(exist_ok=True)

    if hl2_dir is not None:
        for source_path, relative in localization_files(hl2_dir):
            _write(target_root / relative, localization_text(source_path))
            written += 1
        hub = Path(hl2_dir) / HUB_MAP_SOURCE
        if hub.is_file():
            _write(target_root / HUB_MAP_TARGET, hub.read_bytes())
            written += 1
        hudlayout = hudlayout_text(hl2_dir)
        if hudlayout is not None:
            _write(target_root / HUDLAYOUT_TARGET, hudlayout)
            written += 1

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
    configs live in the mod folder too and survive, as does the folder if anything is
    left in it. Warp saves are ours and go.
    """
    return clear_warp_saves(Path(target_root)) + sweep(Path(target_root))


def sweep(directory: Path) -> int:
    """Delete the files this mod owns, then any directory that emptied."""
    if not directory.is_dir():
        return 0

    owned = {relative for _, relative in MOD_FILES} | {DLL_NAME, CLIENT_DLL_NAME, HUDLAYOUT_TARGET,
                                                       HUB_MAP_TARGET}
    removed = 0
    for relative in sorted(owned):
        path = directory / relative
        if path.is_file():
            path.unlink()
            removed += 1

    for path in sorted(directory.glob(LOCALIZATION_TARGET.format("*"))):
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


def installed_game_dir(sourcemods: str | os.PathLike[str] | None = None) -> Path | None:
    """The folder the game actually runs the mod from (where the bridge lives),
    or None when the mod is not installed as a sourcemod."""
    try:
        steam_dir = sourcemod_dir(sourcemods)
    except ValueError:
        return None
    game_dir = proton_game_dir(steam_dir)
    return game_dir if (game_dir / "gameinfo.txt").is_file() else None


# Warp saves the dll writes: `save/apw_<slot key>_<map>.sav`, the key an
# FNV-1a of `<seed>:<slot>` (see ap_game.cpp `SlotKey`).
WARP_SAVE_GLOB = "save/apw_{}_*"


def warp_save_key(slot: str) -> str:
    """The dll's key for a slot's warp saves; empty for no slot."""
    if not slot:
        return ""
    value = 2166136261
    for byte in slot.encode("utf-8"):
        value = ((value ^ byte) * 16777619) & 0xFFFFFFFF
    return f"{value:08x}"


def clear_warp_saves(game_dir: Path, key: str = "*") -> int:
    """Delete one run's warp saves (or every run's). Returns files removed."""
    removed = 0
    for path in sorted(Path(game_dir).glob(WARP_SAVE_GLOB.format(key))):
        if path.is_file():
            path.unlink()
            removed += 1
    return removed


def is_installed(target_root: Path) -> bool:
    """Is there a mod folder with a dll in it?"""
    root = Path(target_root)
    return (root / "gameinfo.txt").is_file() and (root / DLL_NAME).is_file()

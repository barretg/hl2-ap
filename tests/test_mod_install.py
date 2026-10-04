"""Mod install tests: the sourcemod layout, the Proton workaround, gameinfo."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apworld" / "half_life_2"))

import mod  # noqa: E402
from client import bridge  # noqa: E402

linux_only = pytest.mark.skipif(sys.platform == "win32", reason="Proton layout is Linux only")


def test_bridge_and_mod_agree_on_the_store_folder() -> None:
    assert bridge.STORE_SUBDIR == mod.STORE_SUBDIR


def test_mod_folder_name() -> None:
    assert mod.MOD_DIR == "hl2ap"


def test_gameinfo_mounts_retail_hl2_as_a_mod_path() -> None:
    """GameUI reads its menus and cfg/chapter*.cfg from MOD."""
    lines = [l.split() for l in mod.gameinfo_text().decode().splitlines()]
    assert ["game+mod", "|all_source_engine_paths|hl2"] in lines


def test_gameinfo_mounts_hl2_content_only() -> None:
    """Plain HL2: episode content would override HL2's (see game/README.md)."""
    text = mod.gameinfo_text().decode()
    assert "ep2" not in text and "episodic" not in text and "hl2_complete" not in text


def test_gameinfo_paths_made_absolute() -> None:
    text = mod.gameinfo_text("Z:/x/hl2ap/").decode()
    assert "|gameinfo_path|" not in text
    assert "gamebin\t\t\t\tZ:/x/hl2ap/bin" in text


def test_wine_path() -> None:
    assert mod.wine_path(Path("/mnt/lib/sm/hl2ap")) == "Z:/mnt/lib/sm/hl2ap/"


def test_plain_install_and_sweep(tmp_path: Path) -> None:
    target = tmp_path / "hl2ap"
    written, has_dll = mod.install(target, dll=b"dll")
    assert has_dll and written == 2
    assert (target / "bin" / "server.dll").read_bytes() == b"dll"
    assert (target / "archipelago").is_dir()
    assert mod.is_installed(target)

    (target / "save").mkdir()
    (target / "save" / "quick.sav").write_bytes(b"mine")
    (target / "archipelago" / "ap_out.txt").write_text("CHECK|1\n")
    removed = mod.uninstall(target)
    assert removed == 3
    # The player's save survives, and so does the folder holding it.
    assert (target / "save" / "quick.sav").exists()
    assert not (target / "gameinfo.txt").exists()


def test_install_without_a_dll_says_so(tmp_path: Path) -> None:
    written, has_dll = mod.install(tmp_path / "hl2ap")
    assert not has_dll


def test_install_drops_a_stale_client_dll(tmp_path: Path) -> None:
    target = tmp_path / "hl2ap"
    mod.install(target, dll=b"s", client_dll=b"c")
    assert (target / "bin" / "client.dll").exists()
    mod.install(target, dll=b"s")
    assert not (target / "bin" / "client.dll").exists()


def write_libraryfolders(home: Path, libraries: dict[str, list[str]]) -> None:
    vdf = home / ".local" / "share" / "Steam" / "steamapps" / "libraryfolders.vdf"
    vdf.parent.mkdir(parents=True)
    blocks = []
    for i, (path, apps) in enumerate(libraries.items()):
        app_lines = "".join(f'\t\t\t"{a}"\t\t"1"\n' for a in apps)
        blocks.append(f'\t"{i}"\n\t{{\n\t\t"path"\t\t"{path}"\n\t\t"label"\t\t""\n'
                      f'\t\t"apps"\n\t\t{{\n{app_lines}\t\t}}\n\t}}\n')
    vdf.write_text('"libraryfolders"\n{\n' + "".join(blocks) + "}\n")


@linux_only
def test_steam_library_of_finds_hl2(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    write_libraryfolders(tmp_path, {"/home/u/.steam": ["228980"], "/mnt/lib": ["10", "220"]})
    assert mod.steam_library_of() == Path("/mnt/lib")


@linux_only
def test_steam_library_of_missing_app(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    write_libraryfolders(tmp_path, {"/mnt/lib": ["10"]})
    assert mod.steam_library_of() is None


@linux_only
def test_sourcemod_install_under_proton(tmp_path: Path) -> None:
    """Real files where Proton resolves Steam's path, a stub where Steam lists it."""
    library = tmp_path / "lib"
    library.mkdir()
    steam_dir = tmp_path / "sm" / "hl2ap"
    game_dir, written, has_dll = mod.install_sourcemod(steam_dir, dll=b"dll", library=library)

    assert game_dir == library / steam_dir.relative_to("/")
    assert not game_dir.is_symlink()
    assert (game_dir / "bin" / "server.dll").read_bytes() == b"dll"
    assert sorted(p.name for p in steam_dir.iterdir()) == ["gameinfo.txt"]
    # Absolute search paths: drive-relative ones make Wine abort.
    text = (game_dir / "gameinfo.txt").read_text()
    assert "|gameinfo_path|" not in text
    assert mod.wine_path(game_dir) + "bin" in text

    mod.uninstall_sourcemod(steam_dir, library=library)
    assert list(library.iterdir()) == []
    assert not steam_dir.exists()


@linux_only
def test_sourcemod_install_replaces_an_old_symlink(tmp_path: Path) -> None:
    library = tmp_path / "lib"
    library.mkdir()
    steam_dir = tmp_path / "sm" / "hl2ap"
    steam_dir.mkdir(parents=True)
    link = mod.proton_link_path(steam_dir, library)
    link.parent.mkdir(parents=True)
    link.symlink_to(steam_dir)

    game_dir, _, _ = mod.install_sourcemod(steam_dir, dll=b"dll", library=library)
    assert game_dir == link and not game_dir.is_symlink()


def test_sourcemod_install_without_proton(tmp_path: Path, monkeypatch) -> None:
    """Windows (or no HL2 library found): everything in the sourcemod folder."""
    monkeypatch.setattr(mod, "proton_link_path", lambda *a, **k: None)
    steam_dir = tmp_path / "sm" / "hl2ap"
    game_dir, _, has_dll = mod.install_sourcemod(steam_dir, dll=b"dll")
    assert game_dir == steam_dir and has_dll
    assert "|gameinfo_path|" in (steam_dir / "gameinfo.txt").read_text()


def _fake_hl2(root: Path) -> Path:
    resource = root / "hl2" / "resource"
    resource.mkdir(parents=True)
    (resource / "hl2_english.txt").write_bytes("lang".encode("utf-16"))
    (resource / "hl2_french.txt").write_bytes(b"fr")
    (resource / "gameui_english.txt").write_bytes(b"not ours")
    return root


def test_install_copies_hl2_localization_under_the_mod_name(tmp_path: Path) -> None:
    """The engine loads resource/<mod>_<language>.txt only; see LOCALIZATION_SOURCE."""
    hl2 = _fake_hl2(tmp_path / "Half-Life 2")
    target = tmp_path / "hl2ap"
    mod.install(target, hl2_dir=hl2)
    assert (target / "resource" / "hl2ap_english.txt").read_bytes() == "lang".encode("utf-16")
    assert (target / "resource" / "hl2ap_french.txt").read_bytes() == b"fr"
    assert not (target / "resource" / "hl2ap_gameui.txt").exists()

    mod.uninstall(target)
    assert not (target / "resource").exists()


def test_hl2_install_dir(tmp_path: Path) -> None:
    _fake_hl2(tmp_path / "steamapps" / "common" / "Half-Life 2")
    assert mod.hl2_install_dir(tmp_path) == tmp_path / "steamapps" / "common" / "Half-Life 2"
    assert mod.hl2_install_dir(tmp_path / "nowhere") is None

"""The packager: the dlls come from the build, a stale copy in the tree never
wins, and a build without them is refused unless asked for."""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import build_apworld  # noqa: E402


@pytest.fixture
def fake_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    dlls = {}
    for relative in build_apworld.BUILT:
        built = tmp_path / "game" / Path(relative).name
        built.parent.mkdir(exist_ok=True)
        built.write_bytes(b"built " + built.name.encode())
        dlls[relative] = built
    monkeypatch.setattr(build_apworld, "BUILT", dlls)
    return dlls


def test_refuses_without_dlls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(build_apworld, "BUILT", {"mod/files/bin/server.dll": tmp_path / "none"})
    with pytest.raises(SystemExit):
        build_apworld.build(tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_allow_no_dll(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(build_apworld, "BUILT", {"mod/files/bin/server.dll": tmp_path / "none"})
    target = build_apworld.build(tmp_path, allow_no_dll=True)
    assert "half_life_2/mod/files/bin/server.dll" not in zipfile.ZipFile(target).namelist()


def test_layout(tmp_path: Path, fake_build: dict[str, Path]) -> None:
    target = build_apworld.build(tmp_path)
    archive = zipfile.ZipFile(target)
    names = archive.namelist()
    assert target.name == "half_life_2.apworld"
    assert all(n.startswith("half_life_2/") for n in names)
    assert not any("/test/" in n or n.endswith(".pyc") for n in names)
    for relative, built in fake_build.items():
        assert archive.read(f"half_life_2/{relative}") == built.read_bytes()
        assert names.count(f"half_life_2/{relative}") == 1
    manifest = json.loads(archive.read("half_life_2/archipelago.json"))
    assert manifest["game"] == "Half-Life 2"
    assert manifest["version"] == build_apworld.MANIFEST_VERSION
    for required in ("__init__.py", "data/campaign.json", "mod/files/gameinfo.txt",
                     "mod/files/archipelago/checkdata.txt"):
        assert f"half_life_2/{required}" in names

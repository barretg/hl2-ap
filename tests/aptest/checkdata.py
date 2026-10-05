"""The installed `checkdata.txt`, parsed for scenario groups.

Only the records groups use; see `tools/gen_checkdata.py` for the format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Chapter:
    index: int
    key: str
    number: str
    name: str
    maps: list[str]
    is_goal: bool


@dataclass
class Location:
    id: int
    map: str
    kind: str
    arg: str
    name: str
    position: str = ""


@dataclass
class Source:
    """One way to a pickup check: a chapter's first copy."""

    location: int
    map: str
    position: str
    how: str
    # `targetname,input` that brings the copy into existence, or empty.
    spawner: str = ""
    # Confirmed reachable in play though the maps cannot prove it.
    confirmed: bool = False


@dataclass
class CheckData:
    path: Path
    format: int = 0
    data_version: str = ""
    chapters: list[Chapter] = field(default_factory=list)
    locations: dict[int, Location] = field(default_factory=dict)
    sources: list[Source] = field(default_factory=list)
    # classname -> item name, for pickups refused until the item arrives.
    lockable: dict[str, str] = field(default_factory=dict)
    # Progressive item -> its stage count.
    stages: dict[str, int] = field(default_factory=dict)
    # Chapter key -> the vehicle key item its vehicle needs.
    keys: dict[str, str] = field(default_factory=dict)
    # Vehicle upgrade item -> the maps that enable it.
    upgrades: dict[str, list[str]] = field(default_factory=dict)
    hub: str = ""

    def chapter_of(self, map_name: str) -> Chapter:
        for chapter in self.chapters:
            if map_name in chapter.maps:
                return chapter
        raise KeyError(map_name)

    def location_named(self, name: str) -> Location:
        return next(l for l in self.locations.values() if l.name == name)

    def reached(self, map_name: str) -> int:
        return next(l.id for l in self.locations.values()
                    if l.kind == "map_reached" and l.map == map_name)

    def complete(self, chapter_key: str) -> int:
        return next(l.id for l in self.locations.values()
                    if l.kind == "chapter_complete" and l.arg == chapter_key)

    def part_of(self, map_name: str) -> int:
        return self.chapter_of(map_name).maps.index(map_name) + 1


def parse(path: Path) -> CheckData:
    data = CheckData(path)
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        f = line.split("|")
        kind = f[0]
        if kind == "V":
            data.format = int(f[1])
        elif kind == "D":
            data.data_version = f[1]
        elif kind == "C":
            data.chapters.append(Chapter(int(f[1]), f[2], f[3], f[4], f[5].split(","),
                                         f[6] == "1"))
        elif kind == "L":
            data.locations[int(f[1])] = Location(int(f[1]), f[2], f[3], f[4], f[5],
                                                 f[6] if len(f) > 6 else "")
        elif kind == "F":
            data.sources.append(Source(int(f[1]), f[2], f[3], f[4], f[5] if len(f) > 5 else "",
                                       len(f) > 6 and f[6] == "1"))
        elif kind == "K":
            data.lockable[f[1]] = f[2]
        elif kind == "P":
            data.stages[f[1]] = int(f[2])
        elif kind == "H":
            data.keys[f[1]] = f[3]
        elif kind == "U":
            data.upgrades[f[1]] = f[2].split(",")
        elif kind == "B":
            data.hub = f[1]
    return data

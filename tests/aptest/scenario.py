"""What a scenario and a scenario group are, and what a group builds from.

A group is a module in `groups/` exporting `GROUP = Group(...)`. A group may
include others (`includes`), so a phase group runs its subgroups in turn; see
`groups.build`. Its `build`
takes a `Context` and returns the scenarios in a fixed order: append new ones at
the end, never reorder, so `!go <n>` means the same thing between runs (verdicts
are keyed by title, so a reorder loses nothing, it only confuses).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Scenario:
    title: str
    map: str
    # Where to put the player, `x y z`. Empty: wherever the map spawns them.
    pos: str = ""
    steps: str = ""
    # Console commands the test dll runs after placing the player, in order
    # (e.g. `sv_cheats 1`, `ch_createairboat`).
    setup: list[str] = field(default_factory=list)
    # Items taken out of / added to the default held set for this scenario.
    take: list[str] = field(default_factory=list)
    give: list[str] = field(default_factory=list)
    # Items held at exactly this many copies (0 removes), e.g. a gravity gun
    # stage: `{"Progressive Gravity Gun": 2}`.
    counts: dict[str, int] = field(default_factory=dict)
    # Location ids this scenario is waiting for; any other check is called out.
    expect: list[int] = field(default_factory=list)
    # Chapter keys whose COMPLETE/GOAL this scenario is waiting for.
    expect_complete: list[str] = field(default_factory=list)
    # Missions locked for this scenario.
    closed: list[str] = field(default_factory=list)
    # Missions not in this seed at all for this scenario (also locked).
    excluded: list[str] = field(default_factory=list)
    # Locations the server already has (e.g. a part's arrival, for part warps).
    checked: list[int] = field(default_factory=list)
    # What the snapshot says about the client; `!connect`/`!disconnect` change it.
    connected: bool = True
    # Seed options for the snapshot (client.bridge `options`), over the defaults.
    snapshot: dict[str, object] = field(default_factory=dict)
    # The group whose verdict this is. Filled in by `groups.build` with the
    # building group's name unless the group set it: a filtered view of
    # another group (`unproven` of `sources`) names that group, so the two
    # share verdicts.
    origin: str = ""


@dataclass
class Context:
    """What groups build from. `checkdata` (a `checkdata.CheckData`) is None
    when the installed mod has no checkdata.txt."""

    store: Path            # the installed mod's archipelago/ folder
    game_root: Path | None  # the Half-Life 2 install, for groups that read maps
    checkdata: object | None = None
    # Items every scenario holds unless it takes them, name -> count.
    default_items: dict[str, int] = field(default_factory=dict)
    data_version: str = ""


@dataclass(frozen=True)
class Group:
    name: str
    summary: str
    build: Callable[[Context], list[Scenario]]
    # Refuse to run (with a reason) when there is no checkdata.txt yet.
    needs_checkdata: bool = False
    # Former names whose recorded verdicts are this group's.
    aliases: tuple[str, ...] = ()
    # Other groups run as part of this one, after its own scenarios, in this
    # order (a phase group runs its subgroups). A scenario already included
    # once is not repeated, and its verdict is shared with the group it
    # came from wherever it is run.
    includes: tuple[str, ...] = ()


# A line of chat that fits on screen.
CHAT_WIDTH = 120


def reflow(steps: str) -> list[str]:
    """A scenario's steps as whole sentences, one message each.

    Steps are written wrapped to fit the source; sent line by line they read as
    fragments. Lines are joined until one ends a sentence, and an overlong
    sentence is broken between words.
    """
    sentences: list[str] = []
    current = ""
    for line in steps.splitlines():
        line = line.strip()
        if not line:
            continue
        current = f"{current} {line}".strip()
        if current.rstrip("'\")").endswith((".", "!", "?", ":")):
            sentences.append(current)
            current = ""
    if current:
        sentences.append(current)

    out: list[str] = []
    for sentence in sentences:
        while len(sentence) > CHAT_WIDTH:
            cut = sentence.rfind(" ", 0, CHAT_WIDTH)
            if cut <= 0:
                cut = CHAT_WIDTH
            out.append(sentence[:cut])
            sentence = sentence[cut:].strip()
        if sentence:
            out.append(sentence)
    return out

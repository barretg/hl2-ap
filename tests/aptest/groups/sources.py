"""Every way to a pickup check: each chapter's first copy of each weapon (and the
HEV suit), as the data pipeline found it.

The maps prove a copy exists; only play proves a player can get it. Each
scenario loads the copy's map, puts you at it, and asks. A `!fail` here becomes
an `unreachable_copies` entry in `tools/campaigns/hl2.py`.

Built from `checkdata.txt`, so it follows the data: rebuild the data and the
scenarios change with it.
"""

from __future__ import annotations

from scenario import Context, Group, Scenario

# What each way of getting a copy asks the tester to look for.
HOW = {
    "placed": "A {item} lies near where you were placed.",
    "crate": "A supply crate near where you were placed holds a {item}; break it.",
    "drop": "You were placed where an enemy carrying a {item} starts; kill it and "
            "it should drop one (sv_cheats 1 then god, if needed).",
    "ally": "You were placed where an ally carrying a {item} starts; it drops one "
            "if it dies.",
    "give": "The level hands you a {item} in a scripted moment; play to it.",
}


def item_of(ctx: Context, classnames: str) -> str:
    data = ctx.checkdata
    first = classnames.split(",")[0]
    return data.lockable.get(first, first)  # type: ignore[union-attr]


def scenarios_for(ctx: Context, keep) -> list[Scenario]:
    data = ctx.checkdata
    built: list[Scenario] = []
    for source in data.sources:  # type: ignore[union-attr]
        if not keep(source):
            continue
        location = data.locations[source.location]  # type: ignore[union-attr]
        item = item_of(ctx, location.arg)
        chapter = data.chapter_of(source.map)  # type: ignore[union-attr]
        part = data.part_of(source.map)  # type: ignore[union-attr]
        built.append(Scenario(
            title=f"{location.name}: {chapter.name} Part {part} ({source.how})",
            map=source.map,
            pos=source.position,
            steps=f"""
                {HOW[source.how].format(item=item)}
                Ignore the kit at the map's start: it only spawns on a direct map
                load. Could a player reach this {item} in normal play, arriving
                from the previous map? !pass if so, !fail <why> if not, or
                !note <what you saw> if the copy is somewhere else.
            """,
        ))
    return built


GROUP = Group(
    "sources",
    "every chapter's first copy of each pickup check, from checkdata",
    lambda ctx: scenarios_for(ctx, lambda source: True),
    needs_checkdata=True,
)

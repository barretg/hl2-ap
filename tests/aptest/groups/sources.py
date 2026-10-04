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
    "drop": "You were placed where an enemy carrying a {item} starts, and given "
            "a crowbar and a gun; kill it and it should drop one (god, if needed).",
    "ally": "You were placed where an ally carrying a {item} starts; it drops one "
            "if it dies.",
    "give": "The level hands you a {item} in a scripted moment; play to it.",
    "upgrade": "You were placed at the field that turns a held weapon into a "
               "{item}; carry the weapon through it.",
}


def pickup_of(location_name: str) -> str:
    """What lies in the level, from the check's name: `First Gravity Gun` ->
    `Gravity Gun`. Not the item a seed sends (`Progressive Gravity Gun`)."""
    prefix, _, thing = location_name.rpartition("First ")
    return thing if thing else location_name


SPAWNED = ("It only exists once the level spawns it, so the harness spawned it "
           "and turned notarget on; type notarget to have it fight back.")

# Guns handed over for a drop scenario, so the carrier can be killed: the
# first one that is not the weapon being tested.
KILL_WITH = ("weapon_shotgun", "weapon_smg1")


def armed(classnames: str) -> list[str]:
    tested = set(classnames.split(","))
    gun = next(g for g in KILL_WITH if g not in tested)
    return ["sv_cheats 1", "give weapon_crowbar", f"give {gun}"]


def setup_for(source, classnames: str) -> list[str]:
    """Arm the tester for a drop, and spawn a templated copy: placing the
    player skips whatever trigger would have. notarget lets an
    npc_template_maker spawn in plain view."""
    commands = armed(classnames) if source.how in ("drop", "ally") else []
    if source.spawner:
        name, _, input_name = source.spawner.partition(",")
        if "sv_cheats 1" not in commands:
            commands.insert(0, "sv_cheats 1")
        commands += ["notarget", f"ent_fire {name} {input_name}"]
    return commands


def scenarios_for(ctx: Context, keep) -> list[Scenario]:
    """Source scenarios passing `keep`. Their verdicts are always `sources`'s,
    so a filtered view (`unproven`) shares them."""
    data = ctx.checkdata
    built: list[Scenario] = []
    for source in data.sources:  # type: ignore[union-attr]
        if not keep(source):
            continue
        location = data.locations[source.location]  # type: ignore[union-attr]
        item = pickup_of(location.name)
        chapter = data.chapter_of(source.map)  # type: ignore[union-attr]
        part = data.part_of(source.map)  # type: ignore[union-attr]
        built.append(Scenario(
            title=f"{location.name}: {chapter.name} Part {part} ({source.how})",
            map=source.map,
            pos=source.position,
            origin="sources",
            setup=setup_for(source, location.arg),
            steps=f"""
                {HOW[source.how].format(item=item)}
                {SPAWNED if source.spawner else ""}
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

"""Phase 7: Melee Throw."""

from __future__ import annotations

from scenario import Group, Scenario


def build(ctx) -> list[Scenario]:
    return [
        Scenario(
            title="Melee Throw: thrown, hits hard, picked up",
            map="d1_canals_01",
            steps="""
                Hold the crowbar and press secondary fire: it flies forward, spinning,
                and leaves your hands. Throw it at an enemy or a crate: a hit does far
                more than a swing and breaks crates. Walk over it to get it back: no
                Found message, and the harness reports no check (not First Crowbar).
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Melee Throw: comes back by itself",
            map="d1_canals_01",
            steps="""
                Throw the crowbar somewhere you cannot reach. After ten seconds it is in
                your inventory again. The loadout never hands you a second one while it
                is out.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Melee Throw: not without the item",
            map="d1_canals_01", take=["Melee Throw"],
            steps="""
                Secondary fire with the crowbar does nothing, as in retail.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Melee Throw: a quickload with the crowbar out",
            map="d1_canals_01",
            steps="""
                Quicksave, throw the crowbar, quickload: you have one crowbar (in hand
                or back within ten seconds), never two.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Melee: crowbar halves a zombie without fire",
            map="d1_town_01",
            steps="""
                Find a zombie (or aim at the floor and run sv_cheats 1; ent_create
                npc_zombie). Beat it with crowbar swings until it splits, then do the
                same to another with thrown crowbars. Each time the torso crawls at
                you without catching fire.
                !pass or !fail <what happened>.
            """,
        ),
    ]


GROUP = Group("melee", "Melee Throw", build)

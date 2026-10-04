"""Engine basics with our dll: the Phase 0 checklist, plus the harness itself.

Hand-written and needs no checkdata, so it runs before the data pipeline exists.
Positions were read from the retail BSPs (trigger_changelevel bounds).
"""

from __future__ import annotations

from scenario import Group, Scenario


def build(ctx) -> list[Scenario]:
    return [
        Scenario(
            title="Harness: placed, steps shown",
            map="d1_canals_01",
            steps="""
                The map loaded and these steps appeared once you were placed.
                Verbs go in chat (bind a key with: bind y messagemode) or in the
                console as ap_test <verb>, e.g. ap_test info.
                Type !info to show them again and !status for the counts.
                !pass if both work, else !fail <what happened>.
            """,
        ),
        Scenario(
            title="Harness: every verb answers",
            map="d1_canals_01",
            steps="""
                Try each of: !note test, !list, !groups, !give Medkit, !take Medkit,
                !connect, !disconnect, !item Medkit, !trap Headcrab, !deathlink.
                Each should print a reply. !list goes to the console only, with one
                line on screen saying so.
                Also type ap_test info in the console.
                !pass if every one answered, else !fail <which did not>.
            """,
        ),
        Scenario(
            title="Harness: !tp returns to the spot",
            map="d1_canals_01",
            pos="768 2900 -100",
            steps="""
                Walk away a few steps, then type !tp.
                You should be put back where the scenario placed you.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="New game from the menu",
            map="d1_canals_01",
            steps="""
                Open the menu (Esc), pick New Game.
                The chapter list should show Half-Life 2's chapters with real titles,
                and picking Point Insertion should start d1_trainstation_01.
                Menu text should be real words, not #HL2_ tokens.
                !pass or !fail <what you saw>.
            """,
        ),
        Scenario(
            title="Walk across a level transition",
            map="d1_canals_01",
            pos="768 2900 -100",
            steps="""
                The transition to d1_canals_01a is just north of you.
                Walk into it.
                It should load the next map with you in the matching spot, and the
                console should show the hl2ap map line for d1_canals_01a.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Quicksave, cross a transition, quickload",
            map="d1_canals_01",
            pos="768 2900 -100",
            steps="""
                Press quicksave (F6), walk north into the transition to d1_canals_01a,
                then press quickload (F9).
                You should be back on d1_canals_01 where you saved.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Save and load from the menu",
            map="d1_trainstation_02",
            steps="""
                Save from the menu under a new name, move somewhere else, then load it
                from the menu.
                You should be back where you saved.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Die and reload",
            map="d1_canals_01",
            pos="768 2900 -100",
            setup=["kill"],
            steps="""
                You were killed on arrival (the kill command).
                The game should reload the last save (or restart the map) normally.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Airboat across a transition",
            map="d1_canals_07",
            pos="-7100 -4192 -850",
            setup=["sv_cheats 1", "ch_createairboat"],
            steps="""
                An airboat was spawned near you, just east of the exit to d1_canals_08.
                Get in and drive west into the transition.
                You should arrive on d1_canals_08 still in the airboat.
                If the boat is stuck or missing, !note it and drive back toward the
                previous map instead (its transition is near the map start).
                !pass or !fail <what happened>.
            """,
        ),
    ]


GROUP = Group("foundation", "engine basics with our dll, and the harness itself", build)

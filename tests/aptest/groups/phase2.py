"""Phase 2 (data pipeline): its own questions about the data, then the
`sources` subgroup (which covers `unproven`, a view of it).

Its own scenarios settle editorial calls the maps cannot make alone.
"""

from __future__ import annotations

from scenario import Group, Scenario


def build(ctx) -> list[Scenario]:
    return [
        Scenario(
            title="Route Kanal: can it be finished without the airboat?",
            map="d1_canals_05",
            # On the trigger that spawns the airboat and Arlene (d1_canals_05
            # `trigger_arlenespawn_and_autosave`); the dock is just ahead.
            pos="6400 966 -430",
            steps="""
                Walk forward to the dock: the airboat and Arlene appear and she
                opens the gate. Do not get in the boat.
                Try to reach the map's exit to Water Hazard on foot, no noclip.
                The exit is near -4160 -2304 (type getpos to see where you are).
                !pass if you got there on foot, !fail <where you got stuck> if
                the boat is needed. Add !note for anything a seed should know,
                such as needing the boat for only part of the way.
            """,
        ),
    ]


GROUP = Group(
    "phase2",
    "Phase 2 data questions, then its subgroups",
    build,
    includes=("sources", "unproven"),
)

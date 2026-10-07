"""Phase 7: Progressive Aux Power caps the aux meter a quarter per stage."""

from __future__ import annotations

from scenario import Group, Scenario

AUX = "Progressive Aux Power"
RANDOMIZED = {"randomize_aux_power": True}


def stage(n: int, expect: str) -> Scenario:
    return Scenario(
        title=f"Aux power stage {n}",
        map="d2_coast_01", snapshot=RANDOMIZED, counts={AUX: n},
        steps=f"""
            {expect} !status shows the aux power cap. !give {AUX} adds a stage:
            the meter's ceiling rises by a quarter.
            !pass or !fail <what happened>.
        """,
    )


def build(ctx) -> list[Scenario]:
    return [
        stage(0, "The aux meter is empty and stays empty: sprint does not start (the "
                 "no-power sound plays) and the flashlight will not stay on."),
        stage(1, "The aux meter never fills past a quarter: sprint until it empties, "
                 "wait, and it refills only to 25%."),
        stage(2, "The aux meter refills to half and no further."),
        Scenario(
            title="Aux power stage 4 is the full meter",
            map="d2_coast_01", snapshot=RANDOMIZED, counts={AUX: 4},
            steps="""
                The aux meter fills all the way, as in the base game.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Aux power not randomized: full meter with no stages",
            map="d2_coast_01", counts={AUX: 0},
            steps="""
                The seed does not randomize aux power, so with no stages held the meter
                still fills all the way.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Aux power stage 1 underwater and after death",
            map="d1_canals_01", snapshot=RANDOMIZED, counts={AUX: 1},
            steps="""
                Dive and stay under: the meter drains from 25% and you start drowning
                once it is empty. Then die (kill) and respawn: the meter starts at 25%,
                not full.
                !pass or !fail <what happened>.
            """,
        ),
    ]


GROUP = Group("aux_power", "Progressive Aux Power stages", build)

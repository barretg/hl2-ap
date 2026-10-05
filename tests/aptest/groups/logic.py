"""Phase 6: the every-difficulty logic gates, checked in play.

Each scenario takes away what logic says a stretch needs and asks whether it
can be crossed anyway. !pass means the gate is right (you could not go on);
!fail <how> means logic over-asks and the gate should go.
"""

from __future__ import annotations

from scenario import Group, Scenario

GUN = "Progressive Gravity Gun"
TAIL = """
    !pass if you could not go on without it (the gate is right), !fail <how you
    got past> if you could. Noclip is not allowed; cheats only to save time.
"""


def claim(title: str, map_name: str, text: str, **kwargs) -> Scenario:
    return Scenario(title=title, map=map_name, steps=text + TAIL, **kwargs)


def build(ctx) -> list[Scenario]:
    return [
        claim("Black Mesa East needs no gravity gun", "d1_eli_01", """
            Play Black Mesa East with no gravity gun at all. Can you reach the exit to
            Ravenholm? Here !pass means you could NOT (logic must then gate it), and
            !fail means it was fine without one (logic is right as it is).
        """, counts={GUN: 0}),
        claim("Ravenholm needs the gravity gun", "d1_town_01", """
            Play Ravenholm with no gravity gun.
        """, counts={GUN: 0}),
        claim("Highway 17 needs the gravity gun", "d2_coast_01", """
            Play Highway 17 with no gravity gun (the flipped buggy, the crane and
            see-saw puzzles).
        """, counts={GUN: 0}),
        claim("Highway 17 needs its keys past d2_coast_01", "d2_coast_01", """
            Without Highway 17 Car Keys, can you get from d2_coast_01 into
            d2_coast_03 on foot?
        """, take=["Highway 17 Car Keys"]),
        claim("Odessa's gunship needs the RPG", "d2_coast_03", """
            Without the RPG, can you get past New Little Odessa's gunship to
            d2_coast_04?
        """, take=["RPG"]),
        claim("Sandtraps needs the gravity gun", "d2_coast_09", """
            Play Sandtraps with no gravity gun (the plank bridges over the sand).
        """, counts={GUN: 0}),
        claim("Sandtraps needs its keys past d2_coast_09", "d2_coast_09", """
            Without Sandtraps Car Keys, can you get from d2_coast_09 into
            d2_coast_10 on foot?
        """, take=["Sandtraps Car Keys"]),
        claim("Water Hazard needs the Airboat Gun from d1_canals_12", "d1_canals_11", """
            Without the Airboat Gun, can you get through d1_canals_12 and d1_canals_13
            to Black Mesa East (the hunter-chopper)?
        """, take=["Airboat Gun"]),
        claim("Nova Prospekt needs no bugbait", "d2_prison_02", """
            Without bugbait, can you get through Nova Prospekt? Here !pass means you
            could NOT, !fail means it was fine (logic is right as it is).
        """, take=["Bugbait"]),
        claim("Follow Freeman's striders need the RPG", "d3_c17_11", """
            Without the RPG, can you get from d3_c17_11 to the Citadel?
        """, take=["RPG"]),
        claim("Our Benefactors needs stage 3 past the field", "d3_citadel_03", """
            With gravity gun stage 2 only, can you get past the field into
            d3_citadel_04 and on?
        """, counts={GUN: 2}),
    ]


GROUP = Group("logic", "every-difficulty logic gates, checked in play", build)

"""Phase 6: the logic gates, checked in play.

Each scenario takes away what logic says a stretch needs and asks whether it
can be crossed anyway. For an every-difficulty gate, !pass means the gate is
right (you could not go on) and !fail <how> means logic over-asks. For a
strict-only gate (`optional`), !pass means it is right to drop it under loose
logic (you got through) and !fail <where> means it is needed at every
difficulty.
"""

from __future__ import annotations

from scenario import Group, Scenario

GUN = "Progressive Gravity Gun"
TAIL = """
    !pass if you could not go on without it (the gate is right), !fail <how you
    got past> if you could. Noclip is not allowed; cheats only to save time.
"""


OPTIONAL_TAIL = """
    Logic asks for it under strict logic only. !pass if you got through
    without it, !fail <where you got stuck> if you could not. Noclip is not
    allowed; cheats only to save time.
"""


def claim(title: str, map_name: str, text: str, **kwargs) -> Scenario:
    return Scenario(title=title, map=map_name, steps=text + TAIL, **kwargs)


def optional(title: str, map_name: str, text: str, **kwargs) -> Scenario:
    return Scenario(title=title, map=map_name, steps=text + OPTIONAL_TAIL, **kwargs)


def build(ctx) -> list[Scenario]:
    return [
        optional("Highway 17 without the gravity gun", "d2_coast_01", """
            Play Highway 17 with no gravity gun (the flipped buggy, the crane and
            see-saw puzzles).
        """, counts={GUN: 0}),
        optional("Highway 17 on foot", "d2_coast_01", """
            Without Highway 17 Buggy Keys, can you get from d2_coast_01 into
            d2_coast_03 and on to d2_coast_07's exit on foot?
        """, take=["Highway 17 Buggy Keys"]),
        claim("Odessa's gunship needs the RPG", "d2_coast_03", """
            Without the RPG, can you get past New Little Odessa's gunship to
            d2_coast_04?
        """, take=["RPG"]),
        optional("Sandtraps on foot", "d2_coast_09", """
            Without Sandtraps Buggy Keys, can you get from d2_coast_09 into
            d2_coast_10 and on to the beach on foot?
        """, take=["Sandtraps Buggy Keys"]),
        claim("Water Hazard needs the Airboat Gun or the RPG in d1_canals_13", "d1_canals_13", """
            Without the Airboat Gun or the RPG, can you get past the
            hunter-chopper in d1_canals_13 to Black Mesa East?
        """, take=["Airboat Gun", "RPG"]),
        optional("Water Hazard chopper with the RPG only", "d1_canals_13", """
            Without the Airboat Gun but with the RPG, can you bring down the
            hunter-chopper in d1_canals_13 and go on to Black Mesa East?
        """, take=["Airboat Gun"], give=["RPG"]),
        claim("Follow Freeman's striders need the RPG", "d3_c17_11", """
            Without the RPG, can you get from d3_c17_11 to the Citadel?
        """, take=["RPG"]),
        claim("Anticitizen One's generator needs a punt", "d3_c17_07", """
            With gravity gun stage 1 only (no punt), can you shut down the
            generator in d3_c17_07 so the barricade gate opens, and go on to
            d3_c17_08?
        """, counts={GUN: 1}),
        claim("Follow Freeman's Nexus generators need a punt", "d3_c17_10b", """
            With gravity gun stage 1 only (no punt), can you shut down the
            three generators in d3_c17_10b, or reach Health Charger 3,
            Health Charger 5 or Suit Charger 2 there, or go on to d3_c17_11?
        """, counts={GUN: 1}),
        claim("Our Benefactors needs stage 3 past the first ball gate", "d3_citadel_03", """
            With gravity gun stage 2 only, can you get past the first energy-ball
            gate (around x 3500, the shield wall fed by an energy ball) to the
            suit chargers beyond it and on into d3_citadel_04?
        """, counts={GUN: 2}),
    ]


GROUP = Group("logic", "logic gates, checked in play", build)

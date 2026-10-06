"""Phase 5/7: deaths, failed objectives and DeathLink."""

from __future__ import annotations

from scenario import Group, Scenario

FAIL = ["sv_cheats 1", "ent_create player_loadsaved targetname aptest_fail",
        "ent_fire aptest_fail Reload"]


def build(ctx) -> list[Scenario]:
    return [
        Scenario(
            title="A death is reported",
            map="d1_canals_01", snapshot={"death_link": True, "death_link_amnesty": 0},
            steps="""
                Type kill in the console. The harness should show DEATH | Freeman |
                death -> sent, then [aptest] DeathLink sent.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Amnesty forgives deaths, then sends one",
            map="d1_canals_01", snapshot={"death_link": True, "death_link_amnesty": 2},
            steps="""
                Type kill three times, letting the game reload in between. The first
                says it is forgiven with 1 more to go, the second that the next will be
                sent; both show -> forgiven (not sent). The third shows -> sent and [aptest] DeathLink sent, and
                chat says amnesty is back to 2. Further kills repeat the cycle.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="An incoming DeathLink kills, and is not sent back",
            map="d1_canals_01", snapshot={"death_link": True, "death_link_amnesty": 0},
            steps="""
                Type !deathlink. Chat names APTest, you die, and the harness shows no
                DEATH line for it.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="DeathLink off: an incoming one is ignored",
            map="d1_canals_01", snapshot={"death_link": False},
            steps="""
                Type !deathlink. Nothing happens to you.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="A failed objective counts as a death",
            map="d1_canals_01", setup=FAIL,
            snapshot={"death_link": True, "death_link_amnesty": 0},
            steps="""
                The setup fired a player_loadsaved (what an escort failure or a fall
                into the void fires). The screen fades and the save reloads, and the
                harness shows DEATH | Freeman | a failed objective -> sent.
                !pass or !fail <what happened>.
            """,
        ),
    ]


GROUP = Group("deaths", "deaths, failed objectives and DeathLink", build)

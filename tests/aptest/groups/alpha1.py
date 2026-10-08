"""Changes since alpha 1: the Y chat bind, chapter unlock notices and !trace
to level changes."""

from __future__ import annotations

from scenario import Group, Scenario


def build(ctx) -> list[Scenario]:
    return [
        Scenario(
            title="Chat: Y opens it, unless Y is taken",
            map="d2_coast_08",
            steps="""
                Press Y: the chat line opens; Escape closes it. In the console, `bind y`
                shows "messagemode". Then `bind y "+use"`, quit and restart the game:
                `bind y` still shows "+use". `bind y messagemode` to put it back.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Unlocked chapters and an open finale are announced",
            map="d1_canals_01", closed=["d1_town_01", "d3_breen_01"],
            steps="""
                Type !give d1_town_01: chat says We Don't Go to
                Ravenholm... unlocked, with the !warp to get there. Type !give
                d3_breen_01: chat says Dark Energy is open. Finish it to win. Each
                line shows once; !take d1_town_01 then !give d1_town_01 shows it again.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Trace: a part's level change, not the way back",
            map="d1_canals_01",
            steps="""
                Type !trace part 2 reached: the orange line leads on through Route
                Kanal toward the transition to part 2, not back to the transition to
                A Red Letter Day behind you. Where the level has no walkable link the
                line crosses straight over the gap and picks up again beyond it. Walk
                a little way along it: it keeps pointing on.
                Then !warp 3 2 and !trace part 3 reached: the line leads on to part 3,
                not back to part 1.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Aux without HEV: on, sprint works with no suit",
            map="d2_coast_01", take=["HEV Suit"],
            snapshot={"allow_aux_without_hev": True},
            steps="""
                You have no HEV Suit (no armour). Sprint: it works and the aux meter
                drains, then refills. No "No aux power" line in chat.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Aux without HEV: on, Progressive Aux Power still caps it",
            map="d2_coast_01", take=["HEV Suit"],
            snapshot={"allow_aux_without_hev": True, "randomize_aux_power": True},
            counts={"Progressive Aux Power": 1},
            steps="""
                No HEV Suit. Sprint until the meter empties, wait: it refills only to
                a quarter.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Aux without HEV: off, no suit means no aux",
            map="d2_coast_01", take=["HEV Suit"],
            steps="""
                No HEV Suit. Sprint: it does not start, and chat says once: No aux
                power until the HEV Suit item arrives.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Closed captions scale with the screen",
            map="d1_canals_01",
            steps="""
                In the console: cc_subtitles 0; closecaption 1. Wait for a line of
                dialogue or a sound with a caption: the text is about the size of
                the HUD numbers, not tiny. Change resolution: it scales with it.
                !pass or !fail <what happened>.
            """,
        ),
    ]


GROUP = Group("alpha1", "changes since alpha 1", build)

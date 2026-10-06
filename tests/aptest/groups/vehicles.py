"""Phase 6: vehicle keys per chapter, and the Airboat and Buggy Guns."""

from __future__ import annotations

from scenario import Group, Scenario


def build(ctx) -> list[Scenario]:
    return [
        Scenario(
            title="Route Kanal: no boat without its keys",
            map="d1_canals_05", pos="6400 966 -430", take=["Route Kanal Boat Keys"],
            steps="""
                Walk on to the dock: the airboat and Arlene appear. Try to get in:
                refused, chat names Route Kanal Boat Keys (once). Type !give Route Kanal
                Boat Keys and get in.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Water Hazard: keys, and never ejected",
            map="d1_canals_06", take=["Water Hazard Boat Keys"],
            steps="""
                The airboat is beside you. Getting in is refused without Water Hazard
                Boat Keys. !give Water Hazard Boat Keys, get in, then !take Water Hazard
                Boat Keys while seated: you stay in and can drive; only getting back in
                is refused.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Highway 17: no buggy without its keys",
            map="d2_coast_01", take=["Highway 17 Buggy Keys"],
            steps="""
                Find the buggy in the garage. Getting in is refused, naming Highway 17
                Buggy Keys. !give Highway 17 Buggy Keys: you can get in.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Sandtraps: Highway 17's keys do not drive here",
            map="d2_coast_09", take=["Sandtraps Buggy Keys"],
            steps="""
                You hold Highway 17 Buggy Keys but not Sandtraps Buggy Keys. The buggy is
                beside you: getting in is refused, naming Sandtraps Buggy Keys.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="No Airboat Gun item: the mounted gun is silent",
            # d1_canals_11 mounts the gun partway through (the gun cave);
            # d1_canals_13 enables it on the airboat as the map spawns.
            map="d1_canals_13", take=["Airboat Gun"],
            steps="""
                The airboat here has its mounted gun. Get in and press fire: nothing shoots, there is no gun ammo
                on the HUD, and chat says the gun needs the Airboat Gun item (once).
                !give Airboat Gun: the gun charges and fires.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="No Buggy Gun item: the mounted cannon is silent",
            map="d2_coast_09", take=["Buggy Gun"],
            steps="""
                Get in the buggy and press fire, then hold alt-fire: the cannon
                neither fires nor charges, and chat says the gun needs the Buggy Gun
                item (once). !give Buggy Gun: the cannon fires and charges.
                !pass or !fail <what happened>.
            """,
        ),
    ]


GROUP = Group("vehicles", "vehicle keys and the vehicle guns", build)

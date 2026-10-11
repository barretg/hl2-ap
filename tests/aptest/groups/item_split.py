"""`vehicle_keys_per_level` off (one key per vehicle) and `weapons_per_level`
on (a weapon held only in chapters whose own item has arrived)."""

from __future__ import annotations

from scenario import Group, Scenario

from ._helpers import source_at

SHARED_KEYS = {"vehicle_keys_per_level": False}
PER_LEVEL = {"weapons_per_level": True}


def build(ctx) -> list[Scenario]:
    smg = source_at(ctx.checkdata, "SMG", "d1_canals_03")
    return [
        Scenario(
            title="Shared keys: Airboat Keys drive Water Hazard",
            map="d1_canals_06", snapshot=SHARED_KEYS,
            take=["Airboat Keys", "Water Hazard Boat Keys"],
            steps="""
                The airboat is beside you. Getting in is refused, naming Airboat Keys
                (not Water Hazard Boat Keys). !give Water Hazard Boat Keys: still
                refused. !give Airboat Keys: you can get in.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Shared keys: Buggy Keys drive Sandtraps",
            map="d2_coast_09", snapshot=SHARED_KEYS,
            take=["Buggy Keys", "Sandtraps Buggy Keys"],
            steps="""
                The buggy is beside you. Getting in is refused, naming Buggy Keys.
                !give Buggy Keys: you can get in. Open !menu's tracker: the header
                names Buggy Keys as held, and the keys count reads 2/2.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Per-level weapons: only this chapter's SMG counts",
            map="d1_canals_03", pos=smg.position, snapshot=PER_LEVEL,
            take=["Route Kanal SMG"],
            steps="""
                You hold SMG and every other chapter's SMG, but not Route Kanal SMG:
                there is no SMG in your weapons, while the pistol is. An SMG lies
                here: walk over it. Refused, naming Route Kanal SMG. !give Route
                Kanal SMG: the SMG is in your weapons.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Per-level weapons: none where the chapter has no item",
            map="d1_canals_01", snapshot=PER_LEVEL,
            steps="""
                You hold every weapon item, yet Route Kanal has none for the shotgun,
                RPG or crossbow: none of them is in your weapons. Type !hub: in the
                hub you have only the crowbar and the gravity gun. !warp Highway 17:
                the RPG and crossbow are back.
                !pass or !fail <what happened>.
            """,
        ),
    ]


GROUP = Group("item_split", "shared vehicle keys and per-level weapons", build,
              needs_checkdata=True)

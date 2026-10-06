"""Phase 5: what is refused until its item arrives, and what arrives with it."""

from __future__ import annotations

from scenario import Group, Scenario

from ._helpers import first, source_at, spawn_setup


def build(ctx) -> list[Scenario]:
    data = ctx.checkdata
    smg = source_at(data, "SMG", "d1_canals_03")
    rpg = source_at(data, "RPG", "d2_coast_03")
    return [
        Scenario(
            title="A weapon without its item stays where it is",
            map="d1_canals_03", pos=smg.position, take=["SMG"], expect=[first(data, "SMG")],
            steps="""
                An SMG lies here and you do not hold the SMG item. Walk over it.
                It should stay on the ground, chat should say the SMG is not
                received yet (once, not every frame), and the harness should report
                First SMG as the expected check. Then type !give SMG: an SMG should
                appear in your inventory without touching anything.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Items arrive and leave with the snapshot",
            map="d1_canals_01", take=["Shotgun"],
            steps="""
                You hold no shotgun. Type !give Shotgun: chat says Received: Shotgun
                and a shotgun is in your inventory within a second. Type !take Shotgun:
                it is taken away again (your active weapon switches if it was out).
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="A give without the item is refused",
            map="d1_canals_01", counts={"Progressive Gravity Gun": 0},
            setup=["sv_cheats 1", "give weapon_physcannon"],
            expect=[first(data, "Gravity Gun")],
            steps="""
                The setup ran give weapon_physcannon while you hold no Progressive
                Gravity Gun. You should not have the gravity gun, nothing should lie
                at your feet, chat should say it comes when the item does, and the
                harness should report First Gravity Gun.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="A scripted pickup is taken and its scene plays on",
            map="d2_coast_03", pos=rpg.position, take=["RPG"], expect=[first(data, "RPG")],
            setup=spawn_setup(rpg),
            steps="""
                Odessa's RPG was spawned here and you do not hold the RPG item. Walk
                over it: it stays on the ground, the level's pickup scene carries on
                (Odessa's next lines, the train horn), First RPG is reported, and you
                still have no RPG. Then !give RPG: the RPG arrives, and walking over the
                one on the ground gives ammo without replaying the scene.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="No HEV Suit item: no armour, no sprint",
            map="d1_canals_01", take=["HEV Suit"], setup=["sv_cheats 1", "give item_battery"],
            steps="""
                You hold no HEV Suit item. The HUD and weapon selection still work.
                A battery was given: armour should stay at 0. Hold sprint: you do not
                sprint and chat says there is no aux power. Type !give HEV Suit: sprint
                works now, and !item Battery adds armour.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="No Flashlight item: no flashlight",
            map="d1_canals_01", take=["Flashlight"],
            steps="""
                Press the flashlight key: nothing lights and chat says it needs the
                Flashlight item. Type !give Flashlight and press it again: it works.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="The starting crowbar is never taken",
            map="d1_canals_01", take=["Crowbar"],
            steps="""
                The Crowbar item is not held, but the crowbar is a starting item:
                it should still be in your inventory, and stay there.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Weapons survive a transition and a quickload",
            map="d1_canals_01", pos="768 2900 -100",
            steps="""
                Note your weapons. Quicksave, walk north into the transition to
                d1_canals_01a, check your weapons, then quickload. You should hold the
                same weapons in all three places, none duplicated, ammo unchanged.
                !pass or !fail <what happened>.
            """,
        ),
    ]


GROUP = Group("gating", "pickups refused until their item arrives", build, needs_checkdata=True)

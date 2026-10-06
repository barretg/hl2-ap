"""Phase 6: the four Progressive Gravity Gun stages."""

from __future__ import annotations

from scenario import Group, Scenario

from ._helpers import first

GUN = "Progressive Gravity Gun"


def build(ctx) -> list[Scenario]:
    data = ctx.checkdata
    upgrade = data.location_named("First Super Gravity Gun")
    field = next(s for s in data.sources if s.location == upgrade.id and s.how == "upgrade")
    return [
        Scenario(
            title="Stage 0: no gravity gun",
            map="d1_town_01", counts={GUN: 0},
            steps="""
                You have no gravity gun, and none is handed to you.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Stage 1: hold and drop, no punt",
            map="d1_town_01", counts={GUN: 1},
            steps="""
                Pick up a barrel or can with secondary fire, carry it, drop it with
                secondary again. Primary fire (punt or throw) dry-fires, and chat says
                punting needs a second stage (once).
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Stage 2: the normal gravity gun",
            map="d1_town_01", counts={GUN: 2},
            steps="""
                Pick up and punt props as in retail; a zombie cannot be grabbed.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Stage 3 outside the Citadel changes nothing",
            map="d1_town_01", counts={GUN: 3},
            steps="""
                The gun behaves as stage 2 here: not blue, no grabbing zombies.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Stage 2 at the Citadel field: no supercharge",
            map=field.map, pos=field.position, counts={GUN: 2},
            steps="""
                Walk through the confiscation field. Your other weapons dissolve; the
                gravity gun stays the normal orange one (not supercharged), and First
                Super Gravity Gun is not sent. Afterwards your other weapons come back,
                since an orange gun alone cannot get you through the Citadel.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Stage 3 at the Citadel field: super, organics refused",
            map=field.map, pos=field.position, counts={GUN: 3}, expect=[upgrade.id],
            steps="""
                Walk through the field: the gun is supercharged (blue) and First Super
                Gravity Gun is the expected check. Grab and throw props and energy balls:
                they work. Try to grab a soldier or a body: refused, and chat says
                organics need the fourth stage.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Stage 4 at the Citadel field: the full super gravity gun",
            map=field.map, pos=field.position, counts={GUN: 4}, expect=[upgrade.id],
            setup=["sv_cheats 1"],
            steps="""
                Walk through the field. Soldiers can be grabbed, punted and vaporised as
                in retail. A soldier killed by the gun (punted, hit by a thrown prop or
                an energy ball) drops a weapon that dissolves. Look at another and type
                npc_kill: that one's weapon stays on the floor.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Black Mesa East's gravity gun give with stage 0",
            map="d1_eli_02", counts={GUN: 0}, expect=[first(data, "Gravity Gun")],
            steps="""
                Play on until Alyx hands over the gravity gun. You do not get it, it
                lands on the floor in front of you, First Gravity Gun is sent, and the
                scene carries on (Alyx tells you to try it on Dog). Then !give
                Progressive Gravity Gun: the gun arrives and the level goes on.
                !pass or !fail <what happened>.
            """,
        ),
    ]


GROUP = Group("gravity_gun", "the four gravity gun stages", build, needs_checkdata=True)

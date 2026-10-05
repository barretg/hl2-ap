"""Phase 7: what each filler item does on arrival."""

from __future__ import annotations

from scenario import Group, Scenario


def build(ctx) -> list[Scenario]:
    return [
        Scenario(
            title="Ammo Cache tops up every held weapon",
            map="d1_canals_01", setup=["sv_cheats 1", "impulse 101"],
            steps="""
                Fire some pistol and SMG ammo away, then type !item Ammo Cache. Chat says
                every weapon was topped up and your reserve ammo rises.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Medkit heals",
            map="d1_canals_01", setup=["sv_cheats 1", "hurtme 50"],
            steps="""
                You were hurt by 50. Type !item Medkit: +25 health.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Battery adds armour with the suit, not without",
            map="d1_canals_01",
            steps="""
                Type !item Battery: +15 armour. Then !take HEV Suit and !item Battery
                again: chat says there is no suit, and armour drops to 0.
                !pass or !fail <what happened>.
            """,
        ),
    ]


GROUP = Group("filler", "filler items on arrival", build)

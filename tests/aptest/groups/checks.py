"""Phase 5: every kind of check reaches the client, once."""

from __future__ import annotations

from scenario import Group, Scenario

from ._helpers import charger, first, source_at


def build(ctx) -> list[Scenario]:
    data = ctx.checkdata
    health = charger(data, "d1_canals_01", "item_healthcharger")
    suit = charger(data, "d1_canals", "item_suitcharger")
    grenade = source_at(data, "Grenade", "d1_canals_03")
    hev = source_at(data, "HEV Suit", "d1_trainstation_05")
    return [
        Scenario(
            title="Arriving on a map sends Part Reached",
            map="d1_canals_01", expect=[data.reached("d1_canals_01")],
            steps="""
                Chat should say Found: Route Kanal: Part 1 Reached, and the harness
                should report it as the expected check. Type reload in the console
                (not !redo, which starts the scenario afresh): the map loads again and
                the check is not sent again.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="impulse 101 sends no checks",
            map="d1_canals_01", take=["SMG", "RPG"], setup=["sv_cheats 1"],
            steps="""
                Type impulse 101 in the console. You get every weapon you hold the
                item for, but not the SMG or RPG, and nothing lands on the floor.
                The harness reports no First <weapon> check and chat shows no Found.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Using a health charger sends its check",
            map=health.map, pos=health.position, expect=[health.id],
            steps=f"""
                Use the health charger next to you, even at full health.
                Found: {health.name} should show and be the expected check.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Using a suit charger sends its check",
            map=suit.map, pos=suit.position, expect=[suit.id],
            steps=f"""
                Use the suit charger next to you.
                Found: {suit.name} should show and be the expected check.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Touching a weapon sends its First check",
            map="d1_canals_03", pos=grenade.position, expect=[first(data, "Grenade")],
            steps="""
                Walk over the grenade here. You hold the Grenade item, so you pick it
                up, and First Grenade is the expected check.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="The HEV suit pickup sends its check and the scene goes on",
            map="d1_trainstation_05", pos=hev.position, expect=[first(data, "HEV Suit")],
            steps="""
                Pick up the HEV suit in Kleiner's lab. First HEV Suit is the expected
                check, the suit is taken from its stand, and the lab scene continues
                (Kleiner and Alyx talk on) rather than stalling.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Checks wait for the client",
            map="d1_canals_02", connected=False, expect=[data.reached("d1_canals_02")],
            steps="""
                The client reads as disconnected. Chat may say Found, but the harness
                should report no check yet. Type !connect: Part Reached for d1_canals_02
                arrives then.
                !pass or !fail <what happened>.
            """,
        ),
    ]


GROUP = Group("checks", "each kind of check reaches the client", build, needs_checkdata=True)

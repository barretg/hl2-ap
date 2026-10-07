"""Phase 7: what each trap does when it arrives."""

from __future__ import annotations

from scenario import Group, Scenario

# Traps spring five seconds after arriving, counted while the game runs.
WAIT = "Close the console; about five seconds later"


def build(ctx) -> list[Scenario]:
    return [
        Scenario(
            title="NPC Trap: story characters with minds of their own",
            map="d1_canals_01",
            steps=f"""
                Type !trap npc. {WAIT} chat says company has arrived and four characters
                stand around you: story faces (the G-Man, Kleiner, Eli, Breen, Alyx,
                Barney, Mossman, the monk, Odessa), not four copies of one. Watch them for
                half a minute: some follow you, some wander about, some run away from
                you; they talk and react, none attacks you, and none is stuck in a wall
                or the floor. Send it twice more to see other mixes. No crash.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Headcrab Trap: four headcrabs",
            map="d1_canals_01",
            steps=f"""
                Type !trap headcrab. {WAIT} four headcrabs appear around you, spread out,
                on the floor and not in walls, and come for you.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Manhack Swarm Trap: four manhacks",
            map="d1_canals_01",
            steps=f"""
                Type !trap manhack. {WAIT} four manhacks appear around you at head height
                and attack.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Rollermine Trap: three rollermines",
            map="d1_canals_01",
            steps=f"""
                Type !trap rollermine. {WAIT} three rollermines appear on the ground
                around you, spread out and not in walls, and roll at you. The gravity
                gun can pick them up and throw them.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Crow Trap: a dozen crows",
            map="d1_canals_01",
            steps=f"""
                Type !trap crow. {WAIT} about twelve crows land around you, on the
                ground. Walk at them: they hop and fly off.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Junk Trap: props rain down and barely hurt",
            map="d1_canals_01",
            steps=f"""
                Note your health, then type !trap junk. {WAIT} chat says look up and
                about eight props fall on you from overhead: a mix of this map's loose
                props and junk (cans, crates, a watermelon...), no explosive barrels.
                Each hit costs at most 5 health. With 10 health or less (hurtme), it
                never kills. Indoors under a low ceiling they still appear, below it.
                After a minute they fade away.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Butterfingers Trap: the weapon flies, and comes back",
            map="d1_canals_01",
            steps=f"""
                Hold the SMG and type !trap butterfingers. {WAIT} chat says you fumbled
                your SMG and it flies off ahead of you, tumbling, as a physics object
                that bounces and rolls. You switch to another weapon. The loadout does
                not hand the SMG straight back. Walk over it: it is yours again, with its
                magazine, no Found message and the harness reports no check. Do it again
                and leave it: after 30 seconds chat says the suit hands it back, and the
                one on the floor is gone.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Butterfingers Trap: no reissue when the option is off",
            map="d1_canals_01", snapshot={"butterfingers_reissue": False},
            steps=f"""
                Hold the SMG and type !trap butterfingers. {WAIT} the SMG flies. Wait a
                minute without picking it up: it is not handed back. Pick it up: yours
                again, no check.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Butterfingers Trap: waits while driving",
            map="d1_canals_05", setup=["sv_cheats 1", "ch_createairboat"],
            steps=f"""
                Get in the airboat and type !trap butterfingers. Nothing happens while
                you drive. Get out: about a second later you fumble your weapon.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Bunny Hop Trap: fifteen seconds of hopping",
            map="d1_canals_01",
            steps=f"""
                Type !trap bunny. {WAIT} you jump every time you land, for fifteen
                seconds, then stop. Your own jump key still works normally after.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Sticky Key Trap: one key held, named, then let go",
            map="d1_canals_01",
            steps=f"""
                Type !trap sticky. {WAIT} chat names a key (forward, back, strafe left or
                strafe right) and you move that way on your own for fifteen seconds, then
                stop. Send it again and !redo the scenario (a map load) while it is
                held: on the new map you are not still moving.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Reload Trap: reloads from empty, no ammo lost",
            map="d1_canals_01",
            steps=f"""
                Hold the SMG with a full magazine and note the reserve. Type !trap
                reload. {WAIT} the SMG reloads from empty; afterwards the magazine is
                full and magazine plus reserve add up to what they did before. With the
                crowbar in hand, chat says there is nothing to reload.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Traps wait for a level to settle",
            map="d1_canals_01",
            steps="""
                Type !trap headcrab, then at once !redo (the map reloads). The headcrabs
                arrive about five seconds after the new load, not during it, and the game
                does not crash.
                !pass or !fail <what happened>.
            """,
        ),
    ]


GROUP = Group("traps", "traps on arrival", build)

"""Phase 7: what each trap does when it arrives."""

from __future__ import annotations

from scenario import Group, Scenario

# Traps spring five seconds after arriving, counted while the game runs.
WAIT = "Close the console; about five seconds later"


def build(ctx) -> list[Scenario]:
    return [
        Scenario(
            title="NPC Trap: story characters with minds and voices of their own",
            map="d2_coast_01",
            steps=f"""
                Type !trap npc. {WAIT} chat says company has arrived and four characters
                stand around you: story faces (the G-Man, Kleiner, Eli, Breen, Alyx,
                Barney, Mossman, the monk, Odessa), not four copies of one. Some follow
                you, some wander about, some run away from you; none attacks you, and
                none is stuck in a wall or the floor. Look at one and press use: it says a
                line that character has in the game, in their own voice (the G-Man's
                include his "rise and shine" opening). Now and then one nearby speaks
                unprompted. None of them chatters in a citizen's voice. Shoot or crowbar
                one: it dies, whoever it is. Send it twice more for other mixes.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Headcrab Trap: four headcrabs",
            map="d2_coast_01",
            steps=f"""
                Type !trap headcrab. {WAIT} four headcrabs appear around you, spread out,
                on the floor and not in walls, and come for you.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Manhack Swarm Trap: four manhacks",
            map="d2_coast_01",
            steps=f"""
                Type !trap manhack. {WAIT} four manhacks appear around you at head height
                and attack.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Bot Swarm Trap: six bots with crowbars",
            map="d2_coast_01",
            steps=f"""
                Type !trap bot. {WAIT} six bots appear around you on the floor, in mixed
                bodies (citizens, Combine, vortigaunts, zombies). They run about, jump
                over what is in their way, and swing at whatever they bump into, you
                included, a few swings at a time before running off. Humans and Combine
                hold a crowbar. Each dies to a few hits and ragdolls. Map NPCs ignore
                them. Spring it again a few times: new bodies each time, no repeats
                until every model has turned up once.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Mega Bot Swarm Trap: one bot in every body",
            map="d2_coast_01",
            steps=f"""
                Type !trap mega. {WAIT} "MEGA bot swarm!", and a crowd of bots (about 73 on
                a full install), each in a different body, spread out from you and as
                far as they need to. The game keeps running. They behave as the Bot
                Swarm's do.
                !pass or !fail <how many, what happened>.
            """,
        ),
        Scenario(
            title="Spawning traps in a cramped spot: the nearest room, never none",
            map="d1_canals_01",
            steps=f"""
                Squeeze into a tight corner or a narrow passage. Type !trap bot, then
                !trap headcrab, then !trap npc. {WAIT} each announces itself once, and
                all of its spawns appear at the nearest spots they fit (round a corner
                or through a wall if need be), never "no room here". If none fit at
                all, step into the open: the rest arrive within a couple of seconds.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Rollermine Trap: three rollermines",
            map="d2_coast_01",
            steps=f"""
                Type !trap rollermine. {WAIT} three rollermines appear on the ground
                around you, spread out and not in walls, and roll at you. The gravity
                gun can pick them up and throw them.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Crow Trap: a dozen crows",
            map="d2_coast_01",
            steps=f"""
                Type !trap crow. {WAIT} about twelve crows land around you, on the
                ground. Walk at them: they hop and fly off.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Junk Trap: props rain down and barely hurt",
            map="d2_coast_01",
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
            map="d2_coast_01",
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
            title="Butterfingers Trap: several at once, each on its own clock",
            map="d2_coast_01",
            steps=f"""
                Hold the SMG and type !trap butterfingers four times, a few seconds
                apart: four different weapons fly off, one per trap, with no limit.
                Pick up one: yours again, no check, and the others stay withheld. The
                rest come back by themselves 30 seconds after each was dropped, at
                different times.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Butterfingers Trap: no reissue when the option is off",
            map="d2_coast_01", snapshot={"butterfingers_reissue": False},
            steps=f"""
                Hold the SMG and type !trap butterfingers. {WAIT} the SMG flies. Wait a
                minute without picking it up: it is not handed back. Send the trap four
                more times: each throws another weapon. Pick
                them up: yours again, no check. Once you hold nothing at all, the suit
                hands one back.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Butterfingers Trap: a fumbled weapon is never a check after a death",
            map="d2_coast_01",
            steps=f"""
                Hold the crowbar and type !trap butterfingers. {WAIT} it flies. Type
                save fumble, then kill. Once the save reloads you hold the crowbar
                again; walk over the one on the floor: it vanishes and First Crowbar
                is not sent.
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
            map="d2_coast_01",
            steps=f"""
                Type !trap bunny. {WAIT} you jump every time you land, for fifteen
                seconds, then stop. Your own jump key still works normally after.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Sticky Key Trap: one key held, named, then let go",
            map="d2_coast_01",
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
            map="d2_coast_01",
            steps=f"""
                Hold the SMG with a full magazine and note the reserve. Type !trap
                reload. {WAIT} the SMG reloads from empty; afterwards the magazine is
                full and magazine plus reserve add up to what they did before. With the
                RPG in hand (and rockets left) it plays its reload and cannot fire until
                that finishes; no rocket is lost. With the crowbar in hand, chat says
                there is nothing to reload.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Traps wait for a level to settle",
            map="d2_coast_01",
            steps="""
                Type !trap headcrab, then at once !redo (the map reloads). The headcrabs
                arrive about five seconds after the new load, not during it, and the game
                does not crash.
                !pass or !fail <what happened>.
            """,
        ),
    ]


GROUP = Group("traps", "traps on arrival", build)

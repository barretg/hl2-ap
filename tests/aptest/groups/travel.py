"""Phase 5: chapters, the hub, warps, warp saves and the finale."""

from __future__ import annotations

from scenario import Group, Scenario


def build(ctx) -> list[Scenario]:
    data = ctx.checkdata
    hub = data.hub
    return [
        Scenario(
            title="A chapter's exit completes it and returns to the hub",
            map="d1_canals_05", pos="-4160 -2304 -416",
            expect=[data.complete("d1_canals_01")], expect_complete=["d1_canals_01"],
            steps="""
                You were placed in Route Kanal's exit to Water Hazard. Chat should say
                Route Kanal complete, the harness should report its Complete check and
                COMPLETE, and the hub should load instead of d1_canals_06. If nothing
                happened, walk a step to touch the trigger.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="The hub: free to move, nothing to find",
            map=hub,
            steps=f"""
                This is the stand-in hub ({hub}). Your view is your own (not a fixed
                camera), you can walk, nothing hurts you, no weapon lies around, and
                chat says !ap lists chapters. Walk about for a few seconds: no Found
                messages.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="!ap lists every chapter's status",
            map=hub, closed=["d2_coast_01"], excluded=["d1_trainstation_01"],
            checked=[data.complete("d1_canals_01")],
            steps="""
                Type !ap. Point Insertion is not in this seed, Route Kanal complete,
                Highway 17 locked, the rest unlocked and Dark Energy OPEN (the harness
                opens every chapter). The list goes to the console with one line on
                screen if it is long.
                !pass or !fail <what was wrong>.
            """,
        ),
        Scenario(
            title="A locked chapter sends you to the hub",
            map="d1_town_01", closed=["d1_town_01"],
            steps="""
                Ravenholm is locked for this scenario. Shortly after it loads, chat
                should say it is locked and the hub should load. No Part Reached
                check is sent.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="A chapter not in the seed sends you to the hub",
            map="d1_trainstation_01", excluded=["d1_trainstation_01"],
            steps="""
                Point Insertion is not in this seed. Chat should say so and the hub
                should load.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="New Game goes to the hub when Point Insertion is out",
            map="d1_canals_01", excluded=["d1_trainstation_01"],
            steps="""
                Esc, New Game, Point Insertion. The intro may start, then the hub loads
                with the not-in-this-seed message.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="!warp starts an unlocked chapter, and refuses a locked one",
            map=hub, closed=["d2_coast_01"],
            steps="""
                Type !warp 7: refused, Highway 17 is locked. Type !warp we dont go:
                Ravenholm (d1_town_01) loads fresh at its start. Back in the hub with
                !hub, !warp 9a loads Entanglement.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="!warp to a part only once reached",
            map=hub, checked=[data.reached("d1_canals_03")],
            steps="""
                Type !warp 3 5: refused, part 5 of Route Kanal is not reached. Type
                !warp 3 4: d1_canals_03 loads (from a warp save if one was taken, else
                fresh).
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="A warp save is taken on arrival and loaded by a part warp",
            map="d1_canals_02", checked=[data.reached("d1_canals_02")],
            steps="""
                Wait five seconds after arriving: the console shows a save named
                apw_..._d1_canals_02. Walk somewhere, then !hub, then !warp 3 3: you
                arrive where the save was taken, not at the map's start. A second visit
                does not take a new save.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="!setwarp moves the part's warp point; !setwarp <name> adds one",
            map="d1_canals_02", checked=[data.reached("d1_canals_02")],
            steps="""
                Walk somewhere distinctive and type !setwarp: chat says the warp point
                for Route Kanal part 3 is set. !hub, then !warp 3 3: you arrive where
                you typed it. Walk elsewhere, !setwarp bridge, !hub, then !warps lists
                bridge, and !warp bridge brings you there. In the hub, !setwarp alone
                refuses, but !setwarp spot works and !warp spot returns there.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="The way back into a locked chapter is shut",
            map="d1_canals_06", pos="13500 9408 -160", closed=["d1_canals_01"],
            steps="""
                Route Kanal is locked. Walk east into the transition back to
                d1_canals_05: no level change, and chat says Route Kanal is locked
                (once, not every frame).
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="The finale's credits win the run",
            map="d3_breen_01", setup=["sv_cheats 1", "ent_fire logic_ending_credits Trigger"],
            expect=[data.complete("d3_breen_01")], expect_complete=["d3_breen_01"],
            steps="""
                The setup fired the ending credits straight away, so they roll over
                the map's opening scene; ignore the scene. Judge by chat (it should
                congratulate you) and the harness (it should report Dark Energy's
                Complete check and GOAL).
                !pass or !fail <what happened>.
            """,
        ),
    ]


GROUP = Group("travel", "chapters, the hub, warps and the finale", build, needs_checkdata=True)

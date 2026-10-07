"""Phase 7: the navigation menu, !find, !trace and the tracker view."""

from __future__ import annotations

from scenario import Group, Scenario


def build(ctx) -> list[Scenario]:
    return [
        Scenario(
            title="Menu: the - key opens it, 0 closes it",
            map="d2_coast_08",
            steps="""
                Press the - key (minus): a numbered Archipelago menu opens (warp, warp
                points, tracker, find, trace, hub, set warp point). Press 0: it closes.
                Press - twice: it opens and closes. In the console, `bind -` shows
                "ap menu". !menu in chat opens it too.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Menu: a key already bound is left alone",
            map="d2_coast_08",
            steps="""
                In the console: `unbind -`, `bind = "ap menu"`, then quit and restart the
                game. `bind -` shows nothing: the menu stays on =, not bound twice. Then
                `bind - "ap menu"` and `unbind =` to put it back.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Menu: warp to a chapter and a part",
            map="d2_coast_08", closed=["d1_town_01"],
            steps="""
                Menu 1 (Warp to a chapter): only open chapters are listed, with their
                status; Ravenholm is not. 9 shows more when there are over seven, 8 goes
                back. Pick a chapter with one part reached: it starts at once. Pick one
                with several parts reached: a parts page with found counts per part;
                picking a part warps there.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Menu: warp points page",
            map="d2_coast_08",
            steps="""
                Type !setwarp menutest. Menu 2 (Warp points) lists menutest with its
                chapter; picking it warps there.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Find: nearest unfound check, with a bearing",
            map="d2_coast_08",
            steps="""
                Type !find: chat names the nearest unfound check on this map with a
                distance in metres and a direction relative to where you look (ahead,
                to the left, behind...), plus up/down when it is above or below. Turn
                round and !find again: the direction changes to match. !find charger
                limits it to chargers. !find with a name found nowhere on this map
                suggests a !warp to the earliest open part that has one.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Trace: a drawn path, off when found or asked",
            map="d2_coast_08",
            steps="""
                Type !trace: an orange line runs from your feet along walkable ground to
                the nearest unfound check, redrawn as you move. Follow it and collect the
                check: chat says found, trace off, and the line stops. !trace again
                starts a new one; !trace a second time turns it off.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Tracker menu view",
            map="d2_coast_08",
            steps="""
                Menu 3 (or !tracker): the header shows the chapter and part, found/total
                per part, weapons and keys held. Unfound checks on this map are listed;
                picking one traces to it. !tracker charger lists only chargers. The
                console still gets the full listing.
                !pass or !fail <what happened>.
            """,
        ),
    ]


GROUP = Group("navigation", "the navigation menu and finding checks", build)

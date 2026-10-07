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
            title="Trace: a drawn path, off quietly when found or asked",
            map="d2_coast_08",
            steps="""
                Type !trace: an orange line runs from your feet along walkable ground to
                the nearest unfound check, redrawn as you move. Follow it and collect the
                check: chat says only that the check was found, and the line stops.
                !trace again starts a new one; !trace a second time turns it off with
                nothing said in chat.
                !pass or !fail <what happened>.
            """,
        ),
        Scenario(
            title="Tracker: the console listing, as in HL1",
            map="d2_coast_08",
            steps="""
                Type !tracker, close the menu (0) and open the console (~). Chat said
                "[AP] !tracker: N lines in the console (~)." The console has
                "=== Archipelago: location tracker ===", then a heading per part such as
                "Sandtraps, part 2 -- d2_coast_08  (0/3)" with a "[x]"/"[ ]" line per
                check under it, a "Half-Life 2: Weapons" block, and last "Found X of Y
                locations in this seed." !tracker kanal lists only Route Kanal's parts;
                !tracker charger only chargers, the total line unchanged.
                !pass or !fail <what was different>.
            """,
        ),
        Scenario(
            title="Tracker: chapters, parts and checks",
            map="d2_coast_08",
            steps="""
                Menu 3 (or !tracker): it shows the chapter you are in, with its status,
                weapons and keys held, and one line per part with found/total ("(here)"
                on this one), then Weapons, then "Track another chapter". Pick a part:
                its checks, unfound first, then [done] ones. Pick an unfound one here:
                it traces to it. Pick one in another part: chat names the chapter and
                part and the !warp there (or says it is locked or not reached). Pick a
                weapon: chat names the earliest open part that has one. "Track another
                chapter" lists every chapter in the seed with found/total; pick one and
                the tracker follows it, also after a map change. !tracker kanal tracks
                Route Kanal; !tracker charger lists every charger in the seed. 8 always
                goes back a page.
                !pass or !fail <what happened>.
            """,
        ),
    ]


GROUP = Group("navigation", "the navigation menu and finding checks", build)

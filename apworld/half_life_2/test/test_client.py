"""The client: slot data and items in, the snapshot the game reads out."""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from ..client import launcher
from ..client.launcher import HalfLife2Context, outgoing_chat, publish, pump
from ..data import CHAPTERS, ITEMS, LOCATIONS

ITEM_ID = {entry["name"]: entry["id"] for entry in ITEMS}
COMPLETE_ID = {e["trigger"]["chapter"]: e["id"] for e in LOCATIONS
               if e["trigger"]["type"] == "chapter_complete"}

SLOT_DATA = {
    "campaigns": ["hl2"],
    "goal_chapters": {"hl2": "d3_breen_01"},
    "missions_required_by_campaign": {"hl2": 2},
    "starting_chapters": ["d1_canals_01"],
    "excluded_chapters": ["d1_trainstation_01"],
    "excluded_triggers": [],
    "starting_items": ["Crowbar", "HEV Suit", "Flashlight"],
    "melee_throw": True,
    "death_link": True,
    "death_link_amnesty": 3,
}


def item(name: str) -> SimpleNamespace:
    return SimpleNamespace(item=ITEM_ID[name])


class ClientTest(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = tempfile.TemporaryDirectory()
        self.mod = Path(self.dir.name)
        (self.mod / "gameinfo.txt").write_text("x")
        os.environ["HL2AP_MOD_DIR"] = str(self.mod)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        async def make() -> HalfLife2Context:
            return HalfLife2Context(None, None)

        self.ctx = self.loop.run_until_complete(make())
        self.ctx.apply_slot_data(SLOT_DATA)
        self.sent: list = []

        async def send_msgs(msgs):
            self.sent += msgs

        self.ctx.send_msgs = send_msgs

    def tearDown(self) -> None:
        os.environ.pop("HL2AP_MOD_DIR", None)
        self.loop.close()
        self.dir.cleanup()

    def snapshot(self) -> dict[str, str]:
        publish(self.ctx, force=True)
        fields = {}
        for line in (self.mod / "archipelago" / "ap_in.txt").read_text().splitlines():
            if "=" in line and not line.startswith("event="):
                key, _, value = line.partition("=")
                fields[key] = value
        return fields

    def events(self) -> list[str]:
        text = (self.mod / "archipelago" / "ap_in.txt").read_text()
        return [line.split("|")[1] + "|" + line.split("|")[2]
                for line in text.splitlines() if line.startswith("event=")]


class TestSnapshot(ClientTest):
    def test_bridges_through_the_mod_folder(self) -> None:
        self.assertEqual(self.ctx.mod_dir, str(self.mod))
        self.assertIsNotNone(self.ctx.bridge)

    def test_items_counts_and_chapters(self) -> None:
        self.ctx.receive_items({"index": 0, "items": [
            item("Crowbar"), item("HEV Suit"), item("Route Kanal Unlock"),
            item("Progressive Gravity Gun"), item("Progressive Gravity Gun"), item("Shotgun"),
        ]})
        fields = self.snapshot()
        self.assertEqual(fields["chapters"], "d1_canals_01")
        self.assertIn("Shotgun", fields["items"].split(";"))
        self.assertNotIn("Route Kanal Unlock", fields["items"])
        self.assertEqual(fields["counts"], "Progressive Gravity Gun:2")
        self.assertEqual(fields["starting"], "weapon_crowbar")
        self.assertEqual(fields["excluded"], "d1_trainstation_01")
        self.assertEqual(fields["melee_throw"], "1")
        self.assertEqual(fields["death_link"], "1")
        self.assertEqual(fields["death_link_amnesty"], "3")

    def test_resync_rebuilds_rather_than_doubles(self) -> None:
        batch = {"index": 0, "items": [item("Progressive Gravity Gun")]}
        self.ctx.receive_items(batch)
        self.ctx.receive_items(batch)
        self.assertEqual(self.ctx.counts, {"Progressive Gravity Gun": 1})

    def test_filler_never_from_the_backlog(self) -> None:
        self.ctx.receive_items({"index": 0, "items": [item("Ammo Cache")]})
        self.snapshot()
        self.assertEqual(self.events(), [])
        self.ctx.receive_items({"index": 1, "items": [item("Medkit")]})
        self.snapshot()
        self.assertEqual(self.events(), ["ITEM|Medkit"])

    def test_finale_opens_on_the_seal(self) -> None:
        self.ctx.checked_locations = {COMPLETE_ID["d1_canals_01"]}
        self.ctx.sync_completed()
        self.assertNotIn("d3_breen_01", self.ctx.open_chapters)
        self.ctx.checked_locations.add(COMPLETE_ID["d1_canals_06"])
        self.ctx.sync_completed()
        self.assertIn("d3_breen_01", self.ctx.open_chapters)
        self.assertFalse(self.ctx.run_complete)
        self.ctx.completed.add("d3_breen_01")
        self.assertTrue(self.ctx.run_complete)

    def test_a_different_slot_forgets_progress(self) -> None:
        self.ctx.slot, self.ctx.seed_name = 1, "A"
        self.ctx.forget_other_slot()
        self.ctx.completed.add("d1_canals_01")
        self.ctx.forget_other_slot()
        self.assertEqual(self.ctx.completed, {"d1_canals_01"})
        self.ctx.seed_name = "B"
        self.ctx.forget_other_slot()
        self.assertEqual(self.ctx.completed, set())


class TestPump(ClientTest):
    def write_game(self, *lines: str) -> None:
        with (self.mod / "archipelago" / "ap_out.txt").open("a") as handle:
            handle.write("".join(line + "\n" for line in lines))

    def run_pump(self) -> None:
        self.ctx.server = SimpleNamespace(socket=SimpleNamespace(closed=False))
        self.loop.run_until_complete(pump(self.ctx))

    def test_checks_only_for_the_seed(self) -> None:
        self.ctx.missing_locations = {LOCATIONS[0]["id"]}
        self.ctx.checked_locations = set()
        self.write_game(f"CHECK|{LOCATIONS[0]['id']}", f"CHECK|{LOCATIONS[1]['id']}")
        self.run_pump()
        self.assertEqual(self.sent, [{"cmd": "LocationChecks", "locations": [LOCATIONS[0]["id"]]}])

    def test_goal_when_every_finale_is_done(self) -> None:
        self.write_game("GOAL|d3_breen_01")
        self.run_pump()
        self.assertEqual(self.sent[-1]["cmd"], "StatusUpdate")

    def test_forgiven_deaths_stay_home(self) -> None:
        deaths = []

        async def send_death(text):
            deaths.append(text)

        self.ctx.send_death = send_death
        self.ctx.player_names = {}
        self.write_game("DEATH|Freeman|a hunter|1", "DEATH|Freeman|a hunter|0")
        self.run_pump()
        self.assertEqual(len(deaths), 1)


class TestChat(unittest.TestCase):
    def test_outgoing(self) -> None:
        self.assertEqual(outgoing_chat(["Gordon", " hi "]), {"cmd": "Say", "text": "hi"})
        self.assertIsNone(outgoing_chat(["Gordon", "  "]))


class TestComponent(unittest.TestCase):
    def test_registered(self) -> None:
        from worlds.LauncherComponents import components

        self.assertTrue(any(c.display_name == "Half-Life 2 Client" for c in components))
        self.assertTrue(callable(launcher.launch))
        self.assertTrue(CHAPTERS)


class TestRegressions(ClientTest):
    def test_no_slot_data_keeps_the_finale_sealed(self) -> None:
        self.ctx.missions_required_by_campaign = {}
        self.assertNotIn("d3_breen_01", self.ctx.open_chapters)

    def test_slot_identity_uses_the_server_seed(self) -> None:
        self.ctx.slot, self.ctx.seed_name, self.ctx.server_seed_name = 3, None, "S1"
        self.assertEqual(self.ctx.slot_identity, "S1:3")

    def test_slot_identity_without_server_seed_name(self) -> None:
        # Released AP clients have no `server_seed_name`.
        del self.ctx.server_seed_name
        self.ctx.slot, self.ctx.seed_name = 3, "S1"
        self.assertEqual(self.ctx.slot_identity, "S1:3")

    def test_launcher_links_connect(self) -> None:
        from CommonClient import handle_url_arg

        parser = launcher.get_base_parser()
        parser.add_argument("--moddir", default="")
        parser.add_argument("url", nargs="?")
        args = handle_url_arg(parser.parse_args(["archipelago://Gordon:pw@host:1234"]), parser)
        self.assertEqual((args.connect, args.name, args.password), ("Gordon:pw@host:1234", "Gordon", "pw"))
        self.assertIs(launcher.handle_url_arg, handle_url_arg)

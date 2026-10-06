from __future__ import annotations

from ..data import CHAPTERS_BY_KEY
from ..items import unlock_item_for_chapter
from . import HalfLife2TestBase

GRAVITY_GUN = "Progressive Gravity Gun"


def everything_but(test: HalfLife2TestBase, *names: str) -> None:
    """Collect every pool item except all copies of `names`."""
    test.collect([item for item in test.multiworld.itempool
                  if item.player == test.player and item.name not in names])


class TestDefaults(HalfLife2TestBase):
    def test_pool_matches_locations(self) -> None:
        unfilled = [l for l in self.multiworld.get_locations(self.player) if l.item is None]
        pool = [i for i in self.multiworld.itempool if i.player == self.player]
        self.assertEqual(len(unfilled), len(pool))

    def test_four_gravity_gun_stages(self) -> None:
        names = [i.name for i in self.multiworld.itempool]
        self.assertEqual(names.count(GRAVITY_GUN), 4)

    def test_point_insertion_included(self) -> None:
        self.assertNotIn("d1_trainstation_01", self.world.excluded_chapters)
        names = {l.name for l in self.multiworld.get_locations(self.player)}
        self.assertTrue(any(n.startswith("Point Insertion:") for n in names))

    def test_starting_items_precollected(self) -> None:
        held = {i.name for i in self.multiworld.precollected_items[self.player]}
        self.assertTrue({"Crowbar", "HEV Suit", "Flashlight"} <= held)
        self.assertIn(unlock_item_for_chapter[self.world.starting_chapter], held)
        pool = {i.name for i in self.multiworld.itempool}
        self.assertFalse({"Crowbar", "HEV Suit", "Flashlight", "Melee Throw"} & pool)

    def test_starting_chapter_has_no_gate(self) -> None:
        self.assertFalse(CHAPTERS_BY_KEY[self.world.starting_chapter].get("gates"))

    def test_dark_energy_needs_stage_three(self) -> None:
        everything_but(self, GRAVITY_GUN)
        self.assertFalse(self.can_reach_region("d3_breen_01"))
        self.assertFalse(self.can_reach_region("d3_citadel_04"))
        self.assertTrue(self.can_reach_region("d3_citadel_03"))
        for _ in range(3):
            self.collect(self.get_item_by_name(GRAVITY_GUN))
        self.assertTrue(self.can_reach_region("d3_citadel_04"))
        self.assertTrue(self.can_reach_location("Dark Energy: Complete"))
        self.assertBeatable(True)

    def test_super_gravity_gun_check_needs_stage_three(self) -> None:
        everything_but(self, GRAVITY_GUN)
        self.collect(self.get_item_by_name(GRAVITY_GUN))
        self.collect(self.get_item_by_name(GRAVITY_GUN))
        self.assertFalse(self.can_reach_location("First Super Gravity Gun"))
        self.collect(self.get_item_by_name(GRAVITY_GUN))
        self.assertTrue(self.can_reach_location("First Super Gravity Gun"))

    def test_vehicle_keys(self) -> None:
        everything_but(self, "Water Hazard Boat Keys", "Highway 17 Car Keys",
                       "Route Kanal Boat Keys")
        self.assertFalse(self.can_reach_region("d1_canals_06"))
        self.assertTrue(self.can_reach_region("d2_coast_01"))
        self.assertFalse(self.can_reach_region("d2_coast_03"))
        self.assertTrue(self.can_reach_region("d1_canals_05"))
        self.assertFalse(self.can_reach_location("Route Kanal: Complete"))

    def test_airboat_gun(self) -> None:
        everything_but(self, "Airboat Gun")
        self.assertTrue(self.can_reach_region("d1_canals_11"))
        self.assertFalse(self.can_reach_region("d1_canals_12"))

    def test_strict_firepower(self) -> None:
        firearms = ["Pistol", ".357 Magnum", "SMG", "Pulse Rifle", "Shotgun", "Crossbow"]
        everything_but(self, *firearms)
        self.assertFalse(self.can_reach_region("d1_canals_01"))
        self.assertTrue(self.can_reach_region("d1_eli_01"))


class TestLoose(HalfLife2TestBase):
    options = {"logic_difficulty": "loose"}

    def test_firepower_dropped(self) -> None:
        everything_but(self, "Pistol", ".357 Magnum", "SMG", "Pulse Rifle", "Shotgun",
                       "Crossbow")
        self.assertTrue(self.can_reach_region("d3_c17_02"))


class TestEverythingShuffled(HalfLife2TestBase):
    options = {"shuffle_hev_suit": True, "shuffle_flashlight": True, "melee_throw": True}

    def test_items_in_pool(self) -> None:
        pool = {i.name for i in self.multiworld.itempool}
        self.assertTrue({"HEV Suit", "Flashlight", "Melee Throw"} <= pool)
        self.assertIn("Point Insertion Unlock", pool | {
            unlock_item_for_chapter[self.world.starting_chapter]})


class TestNoChargers(HalfLife2TestBase):
    options = {"chargesanity": False}

    def test_no_charger_checks(self) -> None:
        names = {l.name for l in self.multiworld.get_locations(self.player)}
        self.assertFalse(any("Charger" in n for n in names))


class TestOneChapterRequired(HalfLife2TestBase):
    options = {"missions_required": 1}

    def test_seal(self) -> None:
        self.assertEqual(self.world.missions_required_by_campaign["hl2"], 1)

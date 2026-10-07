from __future__ import annotations

from BaseClasses import CollectionState, ItemClassification

from ..data import AUX_POWER, CHAPTERS_BY_KEY
from ..items import filler_items, trap_items, unlock_item_for_chapter
from ..rules import gate_rule
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

    def test_bugbait_not_required(self) -> None:
        bugbait = [i for i in self.multiworld.itempool if i.name == "Bugbait"]
        self.assertTrue(bugbait)
        self.assertFalse(any(i.advancement for i in bugbait))
        everything_but(self, "Bugbait")
        self.assertTrue(self.can_reach_location("Dark Energy: Complete"))

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

    def test_citadel_chargers_past_the_ball_gate(self) -> None:
        everything_but(self, GRAVITY_GUN)
        for _ in range(2):
            self.collect(self.get_item_by_name(GRAVITY_GUN))
        self.assertTrue(self.can_reach_location("Our Benefactors: Suit Charger 1 (Part 3)"))
        self.assertFalse(self.can_reach_location("Our Benefactors: Suit Charger 2 (Part 3)"))
        self.assertFalse(self.can_reach_location("Our Benefactors: Suit Charger 3 (Part 3)"))
        self.collect(self.get_item_by_name(GRAVITY_GUN))
        self.assertTrue(self.can_reach_location("Our Benefactors: Suit Charger 2 (Part 3)"))
        self.assertBeatable(True)

    def test_super_gravity_gun_check_needs_stage_three(self) -> None:
        everything_but(self, GRAVITY_GUN)
        self.collect(self.get_item_by_name(GRAVITY_GUN))
        self.collect(self.get_item_by_name(GRAVITY_GUN))
        self.assertFalse(self.can_reach_location("First Super Gravity Gun"))
        self.collect(self.get_item_by_name(GRAVITY_GUN))
        self.assertTrue(self.can_reach_location("First Super Gravity Gun"))

    def test_gravity_gun_strict_from_ravenholm(self) -> None:
        everything_but(self, GRAVITY_GUN)
        self.assertTrue(self.can_reach_location("Black Mesa East: Complete"))
        self.assertFalse(self.can_reach_region("d1_town_01"))
        self.collect(self.get_item_by_name(GRAVITY_GUN))
        self.assertTrue(self.can_reach_region("d1_town_01"))

    def test_highway_17_strict_gravity_gun(self) -> None:
        everything_but(self, GRAVITY_GUN)
        self.assertFalse(self.can_reach_region("d2_coast_01"))

    def test_vehicle_keys(self) -> None:
        everything_but(self, "Water Hazard Boat Keys", "Highway 17 Buggy Keys",
                       "Route Kanal Boat Keys")
        self.assertFalse(self.can_reach_region("d1_canals_06"))
        self.assertTrue(self.can_reach_region("d2_coast_01"))
        self.assertFalse(self.can_reach_region("d2_coast_03"))
        self.assertTrue(self.can_reach_region("d1_canals_05"))
        self.assertFalse(self.can_reach_location("Route Kanal: Complete"))

    def test_car_keys_strict(self) -> None:
        everything_but(self, "Sandtraps Buggy Keys")
        self.assertFalse(self.can_reach_region("d2_coast_10"))

    def test_airboat_gun(self) -> None:
        everything_but(self, "Airboat Gun")
        self.assertTrue(self.can_reach_region("d1_canals_12"))
        self.assertFalse(self.can_reach_region("d1_canals_13"))

    def test_strict_firepower(self) -> None:
        firearms = ["Pistol", ".357 Magnum", "SMG", "Pulse Rifle", "Shotgun", "Crossbow"]
        everything_but(self, *firearms)
        self.assertFalse(self.can_reach_region("d1_canals_01"))
        self.assertTrue(self.can_reach_region("d1_eli_01"))

    def test_sandtraps_battery(self) -> None:
        everything_but(self, "Buggy Gun", "RPG")
        self.assertTrue(self.can_reach_region("d2_coast_09"))
        self.assertFalse(self.can_reach_region("d2_coast_10"))
        self.collect_by_name("Buggy Gun")
        self.assertTrue(self.can_reach_region("d2_coast_10"))

    def test_buggy_gun_needs_its_buggy(self) -> None:
        rule = gate_rule(self.world, {"any": ["sandtraps battery"]})
        state = CollectionState(self.multiworld)
        state.collect(self.get_item_by_name("Buggy Gun"), True)
        self.assertFalse(rule(state))
        state.collect(self.get_item_by_name("Sandtraps Buggy Keys"), True)
        self.assertTrue(rule(state))

    def test_ravenholm_firepower(self) -> None:
        everything_but(self, "Shotgun", ".357 Magnum", "Pulse Rifle", "Crossbow")
        self.assertTrue(self.can_reach_region("d1_eli_01"))
        self.assertFalse(self.can_reach_region("d1_town_01"))
        self.collect_by_name("Shotgun")
        self.assertTrue(self.can_reach_region("d1_town_01"))


class TestLoose(HalfLife2TestBase):
    options = {"logic_difficulty": "loose"}

    def test_firepower_dropped(self) -> None:
        everything_but(self, "Pistol", ".357 Magnum", "SMG", "Pulse Rifle", "Shotgun",
                       "Crossbow")
        self.assertTrue(self.can_reach_region("d3_c17_02"))

    def test_car_keys_dropped(self) -> None:
        everything_but(self, "Highway 17 Buggy Keys", "Sandtraps Buggy Keys")
        self.assertTrue(self.can_reach_region("d2_coast_03"))
        self.assertTrue(self.can_reach_region("d2_coast_10"))

    def test_highway_17_gravity_gun_dropped(self) -> None:
        everything_but(self, GRAVITY_GUN)
        self.assertTrue(self.can_reach_region("d2_coast_01"))
        self.assertTrue(self.can_reach_region("d2_coast_09"))
        self.assertFalse(self.can_reach_region("d3_citadel_04"))

    def test_highway_17_explosives(self) -> None:
        everything_but(self, "Grenade", "RPG")
        self.assertTrue(self.can_reach_region("d1_town_01"))
        self.assertFalse(self.can_reach_region("d2_coast_01"))
        self.collect_by_name("Grenade")
        self.assertTrue(self.can_reach_region("d2_coast_01"))

    def test_sandtraps_gunship(self) -> None:
        everything_but(self, "RPG")
        self.assertTrue(self.can_reach_region("d2_coast_10"))
        self.assertFalse(self.can_reach_region("d2_coast_11"))

    def test_chopper_airboat_gun_or_rpg(self) -> None:
        everything_but(self, "Airboat Gun")
        self.assertTrue(self.can_reach_region("d1_canals_13"))
        self.remove(self.get_items_by_name("RPG"))
        self.assertFalse(self.can_reach_region("d1_canals_13"))


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


class TestNoTraps(HalfLife2TestBase):
    options = {"trap_percentage": 0}

    def test_no_traps(self) -> None:
        traps = [i for i in self.multiworld.itempool if i.classification & ItemClassification.trap]
        self.assertEqual(traps, [])


class TestAllTraps(HalfLife2TestBase):
    options = {"trap_percentage": 100}

    def test_filler_all_traps(self) -> None:
        filler = [i for i in self.multiworld.itempool if i.name in filler_items]
        traps = [i for i in self.multiworld.itempool if i.name in trap_items]
        self.assertEqual(filler, [])
        self.assertGreater(len(traps), 0)
        self.assertEqual(len(set(trap_items)), 10)


class TestAuxPowerOff(HalfLife2TestBase):
    def test_not_in_pool(self) -> None:
        self.assertNotIn(AUX_POWER, {i.name for i in self.multiworld.itempool})


class TestAuxPowerRandomized(HalfLife2TestBase):
    options = {"randomize_aux_power": True, "starting_aux_power": 1}

    def test_stages_split(self) -> None:
        pooled = [i for i in self.multiworld.itempool if i.name == AUX_POWER]
        started = [i for i in self.multiworld.precollected_items[self.player]
                   if i.name == AUX_POWER]
        self.assertEqual((len(pooled), len(started)), (3, 1))
        self.assertFalse(pooled[0].advancement)


class TestAuxPowerAllStarting(HalfLife2TestBase):
    options = {"randomize_aux_power": True, "starting_aux_power": 4}

    def test_none_in_pool(self) -> None:
        self.assertNotIn(AUX_POWER, {i.name for i in self.multiworld.itempool})

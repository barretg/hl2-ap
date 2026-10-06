"""Half-Life 2.

Chapters, their maps and titles come from the install. What is stated here is
what the maps cannot say.
"""

from __future__ import annotations

from .base import Campaign

HL2 = Campaign(
    key="hl2",
    name="Half-Life 2",
    short="hl2",
    game_dir="hl2",
    resource_file="resource/hl2_english.txt",
    title_key="HL2_Chapter{n}_Title",
    # `chapter14.cfg` loads `credits`, a menu shortcut to the credits roll.
    non_chapters=frozenset({"14"}),
    goal_chapter="d3_breen_01",
    excluded_maps=frozenset({
        # Menu backgrounds, the credits roll and the intro cinematic.
        "background01", "background02", "background03", "background04",
        "background05", "background06", "background07", "credits", "intro",
        # Cut from the game; Valve ships a 0-byte placeholder.
        "d2_coast_02",
        # A commentary-era copy of d3_c17_02 that no changelevel leads to.
        "d3_c17_02_camera",
    }),
    weapons={
        "Crowbar": ["weapon_crowbar"],
        "Gravity Gun": ["weapon_physcannon"],
        "Pistol": ["weapon_pistol"],
        ".357 Magnum": ["weapon_357"],
        "SMG": ["weapon_smg1"],
        "Pulse Rifle": ["weapon_ar2"],
        "Shotgun": ["weapon_shotgun"],
        "Crossbow": ["weapon_crossbow"],
        "Grenade": ["weapon_frag"],
        "RPG": ["weapon_rpg"],
        "Bugbait": ["weapon_bugbait"],
    },
    # The confiscation field in d3_citadel_03.
    upgrades={"Super Gravity Gun": ("Gravity Gun", "trigger_weapon_dissolve",
                                    "OnChargingPhyscannon")},
    confiscating_upgrade="Super Gravity Gun",
    # The flashlight has no pickup: the item lets the flashlight key work.
    equipment={"HEV Suit": ["item_suit"], "Flashlight": []},
    equipment_classification={"Flashlight": "useful"},
    enemy_npcs=frozenset({"npc_combine_s", "npc_metropolice"}),
    ally_npcs=frozenset({"npc_citizen", "npc_barney", "npc_alyx", "npc_monk"}),
    input_gives={"ExtractBugbait": "weapon_bugbait"},
    vehicles={"scripts/vehicles/airboat.txt": "Boat",
              "scripts/vehicles/jeep_test.txt": "Car"},
    # Verdicts from the `sources` harness group (2026-10-04) unless noted.
    unreachable_copies={
        # Point Insertion's and A Red Letter Day's metrocops are scripted and
        # the player is unarmed until Barney's crowbar in d1_trainstation_06.
        "Pistol": [f"d1_trainstation_0{n}" for n in range(1, 6)],
        "SMG": [f"d1_trainstation_0{n}" for n in range(1, 6)] + [
            # Black Mesa East's staged cop-versus-vortigaunt fight: scenery.
            "d1_eli_02@528 2400 -2735",
            # The pod ride; nothing killed there drops within reach.
            "d3_citadel_02",
            # (From the confiscation field on, see confiscating_upgrade.)
        ],
        # Out of reach; the soldiers spawning near -1227 7817 192 are not.
        # (From the Citadel's confiscation field on, see confiscating_upgrade.)
        "Pulse Rifle": [
            "d3_c17_10a@96 6208 289",
            # The soldier Alyx shoots at the Entanglement meetup falls where
            # the player never goes (2026-10-04).
            "d2_prison_06@1424 369 -488",
        ],
        # Dark Energy's suit is part of a scripted sequence.
        "HEV Suit": ["d3_breen_01"],
    },
    confirmed_copies={
        # The vortigaunt extracts it after the antlion guard; scripted.
        "Bugbait": ["d2_coast_11"],
        # Breen's office hands the gun back in a scripted sequence.
        "Super Gravity Gun": ["d3_breen_01"],
    },
    chargers={"item_healthcharger": "Health Charger", "item_suitcharger": "Suit Charger"},
    # Logic, first cut (2026-10-04). Traversal needs (keys, gravity gun
    # stages, the RPG where a gunship or strider bars the way, the Airboat
    # Gun) apply at every difficulty; firepower is strict only. Each gate
    # here is a claim the `logic` harness group checks in play.
    starting_items=["Crowbar"],
    requirement_groups={
        "firearm": ["Pistol", ".357 Magnum", "SMG", "Pulse Rifle", "Shotgun", "Crossbow"],
        "heavy": ["SMG", "Pulse Rifle", "Shotgun"],
    },
    gates={
        # Armed cops and manhacks; the airboat is how the chapter ends.
        "d1_canals_01": {"entry": {"strict": ["firearm"]},
                         "complete": {"items": {"Route Kanal Boat Keys": 1}}},
        # Played in the boat from the first map; the hunter-chopper is
        # killed with the mounted gun in d1_canals_13 (assumed from d1_canals_12).
        "d1_canals_06": {"entry": {"strict": ["firearm"],
                                   "items": {"Water Hazard Boat Keys": 1}},
                         "maps": {"d1_canals_12": {"items": {"Airboat Gun": 1}}}},
        # Physics puzzles throughout.
        "d1_town_01": {"entry": {"strict": ["firearm"],
                                 "items": {"Progressive Gravity Gun": 1}}},
        # The buggy is handed over in d2_coast_01; Odessa's gunship in
        # d2_coast_03 needs the RPG to move on.
        "d2_coast_01": {"entry": {"strict": ["heavy"],
                                  "items": {"Progressive Gravity Gun": 1}},
                        "maps": {"d2_coast_03": {"items": {"Highway 17 Car Keys": 1}},
                                 "d2_coast_04": {"items": {"RPG": 1}}}},
        # Driven from the first map to the beach; plank bridges over the sand.
        "d2_coast_09": {"entry": {"strict": ["heavy"],
                                  "items": {"Progressive Gravity Gun": 1}},
                        "maps": {"d2_coast_10": {"items": {"Sandtraps Car Keys": 1}}}},
        "d2_prison_02": {"entry": {"strict": ["heavy"]}},
        "d2_prison_06": {"entry": {"strict": ["heavy"]}},
        "d3_c17_02": {"entry": {"strict": ["heavy"]}},
        # Gunships and the striders at the end.
        "d3_c17_09": {"entry": {"strict": ["heavy"]},
                      "maps": {"d3_c17_11": {"items": {"RPG": 1}}}},
        # Past the confiscation field only the supercharged gun works.
        "d3_citadel_01": {"maps": {"d3_citadel_04": {"items": {"Progressive Gravity Gun": 3}}}},
        "d3_breen_01": {"entry": {"items": {"Progressive Gravity Gun": 3}}},
    },
    # The supercharge is withheld below stage 3.
    source_gates={"Super Gravity Gun": {"items": {"Progressive Gravity Gun": 3}}},
)

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
    # Nova Prospekt can be done without the Bugbait (2026-10-06).
    item_classification={"Flashlight": "useful", "Bugbait": "useful"},
    enemy_npcs=frozenset({"npc_combine_s", "npc_metropolice"}),
    ally_npcs=frozenset({"npc_citizen", "npc_barney", "npc_alyx", "npc_monk"}),
    input_gives={"ExtractBugbait": "weapon_bugbait"},
    vehicles={"scripts/vehicles/airboat.txt": "Boat",
              "scripts/vehicles/jeep_test.txt": "Buggy"},
    # Found unreachable in play (2026-10-07).
    unreachable_chargers={
        "d1_trainstation_01": {("item_suitcharger", (-3649, -425, 24))},
    },
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
    # Logic, first cut (2026-10-04). Traversal needs (boat keys, gravity gun
    # stages, the RPG where a gunship or strider bars the way, the Airboat
    # Gun) apply at every difficulty; firepower, buggy keys and the gravity gun
    # where it only helps are strict only. Each gate
    # here is a claim the `logic` harness group checks in play.
    starting_items=["Crowbar"],
    requirement_groups={
        "firearm": ["Pistol", ".357 Magnum", "SMG", "Pulse Rifle", "Shotgun", "Crossbow"],
        "heavy": ["SMG", "Pulse Rifle", "Shotgun"],
        # Ravenholm's zombies need the shotgun or better; the RPG has too few
        # shots (2026-10-06).
        "zombie killer": ["Shotgun", ".357 Magnum", "Pulse Rifle", "Crossbow"],
        "gravity gun": ["Progressive Gravity Gun"],
        # The buggy chapters can in theory be run on foot (2026-10-06).
        "highway 17 buggy": ["Highway 17 Buggy Keys"],
        "sandtraps buggy": ["Sandtraps Buggy Keys"],
        "airboat gun": ["Airboat Gun"],
        # The hunter-chopper can also be brought down with the RPG, and with
        # neither it cannot (confirmed in play, 2026-10-06).
        "chopper killer": ["Airboat Gun", "RPG"],
        "explosives": ["Grenade", "RPG"],
        # Sandtraps' battery is reached by blasting its way with the buggy's
        # cannon or the RPG (2026-10-06).
        # The gun only counts with the buggy it is mounted on.
        "sandtraps battery": [["Buggy Gun", "Sandtraps Buggy Keys"], "RPG"],
    },
    gates={
        # Armed cops and manhacks; the airboat is how the chapter ends.
        "d1_canals_01": {"entry": {"strict": ["firearm"]},
                         "complete": {"items": {"Route Kanal Boat Keys": 1}}},
        # Played in the boat from the first map; the hunter-chopper in
        # d1_canals_13 is killed with the mounted gun, or the RPG under loose
        # logic (2026-10-06).
        "d1_canals_06": {"entry": {"strict": ["firearm"],
                                   "items": {"Water Hazard Boat Keys": 1}},
                         "maps": {"d1_canals_13": {"strict": ["airboat gun"],
                                                   "any": ["chopper killer"]}}},
        # Black Mesa East goes on without Alyx's gravity gun (props stack),
        # and Ravenholm is passable without it too (2026-10-06).
        "d1_town_01": {"entry": {"strict": ["zombie killer", "gravity gun"]}},
        # The buggy is handed over flipped in d2_coast_01, and parts of the
        # chapter need it: explosives flip it at any difficulty, with the
        # gravity gun as well under strict logic. Odessa's gunship in
        # d2_coast_03 needs the RPG to move on (2026-10-06).
        "d2_coast_01": {"entry": {"strict": ["heavy", "gravity gun"],
                                  "any": ["explosives"]},
                        "maps": {"d2_coast_03": {"strict": ["highway 17 buggy"]},
                                 "d2_coast_04": {"items": {"RPG": 1}}}},
        # Driven from the first map to the beach; plank bridges over the sand,
        # which the gravity gun only helps with. Fine on foot under loose logic. Under strict, the buggy, and the
        # Buggy Gun or the RPG to get the battery that lets it into
        # d2_coast_10 (2026-10-06).
        "d2_coast_09": {"entry": {"strict": ["heavy", "gravity gun"]},
                        # Part 2's gunship (d2_coast_10) needs the RPG to move
                        # on, at any difficulty (2026-10-06).
                        "maps": {"d2_coast_10": {"strict": ["sandtraps buggy",
                                                          "sandtraps battery"]},
                                 "d2_coast_11": {"items": {"RPG": 1}}}},
        "d2_prison_02": {"entry": {"strict": ["heavy"]}},
        "d2_prison_06": {"entry": {"strict": ["heavy"]}},
        # d3_c17_04's metal panel over the hopper pit is frozen until the
        # gravity gun grabs it (spawnflags 72); the map's only check is
        # reaching it (2026-10-08).
        # d3_c17_07's barricade gate opens once its generator is shut down,
        # which takes a punt: stage 2 for d3_c17_08 (2026-10-10).
        "d3_c17_02": {"entry": {"strict": ["heavy"]},
                      "maps": {"d3_c17_05": {"items": {"Progressive Gravity Gun": 1}},
                               "d3_c17_08": {"items": {"Progressive Gravity Gun": 2}}}},
        # Gunships and the striders at the end. d3_c17_10b's three Nexus
        # generators are punted off to drop its forcefields: stage 2 for
        # d3_c17_11 (2026-10-10).
        "d3_c17_09": {"entry": {"strict": ["heavy"]},
                      "maps": {"d3_c17_11": {"items": {"RPG": 1,
                                                       "Progressive Gravity Gun": 2}}}},
        # Past the confiscation field only the supercharged gun works.
        "d3_citadel_01": {"maps": {"d3_citadel_04": {"items": {"Progressive Gravity Gun": 3}}}},
        "d3_breen_01": {"entry": {"items": {"Progressive Gravity Gun": 3}}},
    },
    # The supercharge is withheld below stage 3.
    source_gates={"Super Gravity Gun": {"items": {"Progressive Gravity Gun": 3}}},
    # d3_citadel_03 runs from the field (x 7700) to the exit (x 720); its
    # first energy-ball gate (x 3500) needs the supercharged gun, so the
    # chargers past it do too (2026-10-06).
    check_gates={
        "Our Benefactors: Suit Charger 2 (Part 3)": {"items": {"Progressive Gravity Gun": 3}},
        "Our Benefactors: Suit Charger 3 (Part 3)": {"items": {"Progressive Gravity Gun": 3}},
        # Past d3_c17_10b's forcefields (y -20 and y 59), which drop only once
        # all three generators are punted off (2026-10-10).
        "Follow Freeman!: Health Charger 3 (Part 3)": {"items": {"Progressive Gravity Gun": 2}},
        "Follow Freeman!: Health Charger 5 (Part 3)": {"items": {"Progressive Gravity Gun": 2}},
        "Follow Freeman!: Suit Charger 2 (Part 3)": {"items": {"Progressive Gravity Gun": 2}},
    },
)

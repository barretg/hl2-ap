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
    intro_chapter="d1_trainstation_01",
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
    equipment={"HEV Suit": ["item_suit"]},
    enemy_npcs=frozenset({"npc_combine_s", "npc_metropolice"}),
    ally_npcs=frozenset({"npc_citizen", "npc_barney", "npc_alyx", "npc_monk"}),
    input_gives={"ExtractBugbait": "weapon_bugbait"},
    vehicles={"scripts/vehicles/airboat.txt": "Boat",
              "scripts/vehicles/jeep_test.txt": "Car"},
    # Point Insertion's and A Red Letter Day's metrocops are scripted and the
    # player is unarmed until Barney's crowbar in d1_trainstation_06.
    unreachable_copies={
        "Pistol": [f"d1_trainstation_0{n}" for n in range(1, 6)],
        "SMG": [f"d1_trainstation_0{n}" for n in range(1, 6)],
    },
    chargers={"item_healthcharger": "Health Charger", "item_suitcharger": "Suit Charger"},
)

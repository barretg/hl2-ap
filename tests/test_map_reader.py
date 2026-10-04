"""The Source map reader and the entity I/O analysis, on synthetic maps."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import bsp_entities as bsp  # noqa: E402
from map_logic import MapLogic  # noqa: E402


def make_bsp(path: Path, entity_text: str, models: list[tuple[tuple, tuple]] = ()) -> Path:
    """A minimal v20 VBSP: entity and model lumps, every other lump empty."""
    entity_lump = entity_text.encode("latin-1") + b"\0"
    model_lump = b"".join(struct.pack("<3f3f3f3i", *mins, *maxs, 0, 0, 0, 0, 0, 0)
                          for mins, maxs in models)
    offset = bsp.HEADER_SIZE
    lumps = [(0, 0)] * bsp.LUMP_COUNT
    lumps[bsp.LUMP_ENTITIES] = (offset, len(entity_lump))
    lumps[bsp.LUMP_MODELS] = (offset + len(entity_lump), len(model_lump))
    header = struct.pack("<4si", b"VBSP", 20)
    for lump_offset, length in lumps:
        header += struct.pack("<iii4s", lump_offset, length, 0, b"\0\0\0\0")
    header += struct.pack("<i", 1)
    path.write_bytes(header + entity_lump + model_lump)
    return path


def test_repeated_keys_kept_in_order(tmp_path: Path) -> None:
    text = '{\n"classname" "trigger_once"\n"OnTrigger" "a,Enable,,0,-1"\n' \
           '"OnTrigger" "b,Kill,,1.5,1"\n}\n'
    entity = bsp.load_map(make_bsp(tmp_path / "m.bsp", text))[0]
    assert entity.all("OnTrigger") == ["a,Enable,,0,-1", "b,Kill,,1.5,1"]
    outputs = entity.outputs()
    assert [(name, o.target, o.input, o.delay, o.times) for name, o in outputs] == [
        ("OnTrigger", "a", "Enable", 0.0, -1), ("OnTrigger", "b", "Kill", 1.5, 1)]


def test_braces_inside_values(tmp_path: Path) -> None:
    text = '{\n"classname" "info_target"\n"message" "a { b } c"\n}\n'
    entity = bsp.load_map(make_bsp(tmp_path / "m.bsp", text))[0]
    assert entity.get("message") == "a { b } c"


def test_empty_and_truncated_maps_fail(tmp_path: Path) -> None:
    empty = tmp_path / "empty.bsp"
    empty.write_bytes(b"")
    with pytest.raises(bsp.BspError, match="too short"):
        bsp.load_map(empty)
    good = make_bsp(tmp_path / "m.bsp", '{\n"classname" "worldspawn"\n}\n')
    truncated = tmp_path / "cut.bsp"
    truncated.write_bytes(good.read_bytes()[:-4])
    with pytest.raises(bsp.BspError, match="past the end"):
        bsp.load_map(truncated)


def test_brush_entity_position_is_bounds_centre_plus_origin(tmp_path: Path) -> None:
    text = '{\n"classname" "worldspawn"\n}\n{\n"classname" "func_door"\n"model" "*1"\n' \
           '"origin" "10 0 0"\n}\n'
    path = make_bsp(tmp_path / "m.bsp", text,
                    [((0, 0, 0), (1, 1, 1)), ((0, 0, 0), (100, 50, 20))])
    entities, bounds = bsp.load_map(path), bsp.brush_model_bounds(path)
    assert bsp.world_position(entities[1], bounds) == (60.0, 25.0, 10.0)


def entities(*blocks: dict[str, str | list[str]]) -> list[bsp.Entity]:
    result = []
    for block in blocks:
        pairs = []
        for key, value in block.items():
            for v in value if isinstance(value, list) else [value]:
                pairs.append((key, v))
        result.append(bsp.Entity(pairs))
    return result


def test_cold_load_kit_through_entity_maker_and_relay() -> None:
    ents = entities(
        {"classname": "logic_auto", "OnNewGame": "relay,Trigger,,0,-1"},
        {"classname": "logic_relay", "targetname": "relay", "OnTrigger": "maker,ForceSpawn,,0,-1"},
        {"classname": "env_entity_maker", "targetname": "maker", "EntityTemplate": "kit"},
        {"classname": "point_template", "targetname": "kit", "Template01": "kit_item*"},
        {"classname": "weapon_crowbar", "targetname": "kit_item_crowbar"},
        {"classname": "weapon_pistol", "targetname": "loose"},
    )
    logic = MapLogic(ents)
    assert not logic.exists_in_play(4)
    assert logic.exists_in_play(5)


def test_template_spawned_in_play_is_real() -> None:
    ents = entities(
        {"classname": "trigger_once", "OnTrigger": "tmpl,ForceSpawn,,0,1"},
        {"classname": "point_template", "targetname": "tmpl", "Template01": "rpg"},
        {"classname": "weapon_rpg", "targetname": "RPG"},
    )
    logic = MapLogic(ents)
    assert 2 in logic.templated
    assert logic.exists_in_play(2)


def test_receives_and_inputs_to() -> None:
    ents = entities(
        {"classname": "logic_relay", "OnTrigger": ["boat,EnableGun,,0,1", "cmd,Command,give x,0,1"]},
        {"classname": "prop_vehicle_airboat", "targetname": "Boat"},
        {"classname": "point_clientcommand", "targetname": "cmd"},
    )
    logic = MapLogic(ents)
    assert logic.inputs_to({"prop_vehicle_airboat"}, "enablegun") == [1]
    assert logic.receives(2, "Command") == ["give x"]

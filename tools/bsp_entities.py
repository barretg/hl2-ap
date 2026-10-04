"""Read the entity lump and brush model bounds out of Source (VBSP) maps.

Half-Life 2's own maps are the authoritative source for what exists in each
level: the changelevels that chain them, the weapons and chargers lying in
them, the scripted gives. The campaign data is read straight out of them rather
than written from memory.

Source differs from GoldSrc in two ways that matter here. Keys repeat within an
entity: every output (`OnTrigger`, `OnPlayerPickup`) is its own keyvalue, so an
entity is kept as its ordered pairs and a last-wins view of them. And the map
header is fixed at 64 lumps with a version per lump; a lump with a nonzero
fourCC is LZMA compressed, which retail HL2 never does and is refused here
rather than misread.

Usage:
    python tools/bsp_entities.py <bsp-or-directory> [--classname weapon_*] [--full]
    python tools/bsp_entities.py d1_canals_01.bsp --classname trigger_changelevel --full
    python tools/bsp_entities.py maps/ --counts
    python tools/bsp_entities.py d1_canals_01.bsp --raw > entities.txt
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

LUMP_ENTITIES = 0
LUMP_MODELS = 14
LUMP_COUNT = 64
HEADER_FMT = "<4si" + "iii4s" * LUMP_COUNT + "i"
HEADER_SIZE = struct.calcsize(HEADER_FMT)
SUPPORTED_VERSIONS = (19, 20)
# dmodel_t: mins, maxs, origin (3 floats each), headnode, firstface, numfaces.
MODEL_STRUCT_SIZE = 48

Vec3 = tuple[float, float, float]


class BspError(ValueError):
    """A file that is not a readable Source map."""


def lump_table(data: bytes, name: str) -> list[tuple[int, int]]:
    """`(offset, length)` per lump. Fails loudly on anything not a whole map.

    Valve ships some cut maps as 0-byte placeholders (`d2_coast_02`); those and
    truncated files are errors, so a caller decides whether to skip them.
    """
    if len(data) < HEADER_SIZE:
        raise BspError(f"{name}: {len(data)} bytes, too short to be a BSP")
    fields = struct.unpack_from(HEADER_FMT, data)
    if fields[0] != b"VBSP":
        raise BspError(f"{name}: not a VBSP file (magic {fields[0]!r})")
    if fields[1] not in SUPPORTED_VERSIONS:
        raise BspError(f"{name}: unsupported BSP version {fields[1]}")
    table = []
    for index in range(LUMP_COUNT):
        offset, length, _version, fourcc = fields[2 + index * 4: 6 + index * 4]
        if offset < 0 or length < 0 or offset + length > len(data):
            raise BspError(f"{name}: lump {index} runs past the end of the file")
        if index in (LUMP_ENTITIES, LUMP_MODELS) and fourcc != b"\0\0\0\0":
            raise BspError(f"{name}: lump {index} is compressed, which is not supported")
        table.append((offset, length))
    return table


def read_lump(bsp_path: Path, index: int) -> bytes:
    data = bsp_path.read_bytes()
    offset, length = lump_table(data, bsp_path.name)[index]
    return data[offset:offset + length]


def read_entity_lump(bsp_path: Path) -> str:
    raw = read_lump(bsp_path, LUMP_ENTITIES)
    return raw.split(b"\x00", 1)[0].decode("latin-1")


@dataclass
class Entity:
    """One entity: its keyvalues in file order, and a last-wins lookup."""

    pairs: list[tuple[str, str]] = field(default_factory=list)

    def get(self, key: str, default: str = "") -> str:
        for k, v in reversed(self.pairs):
            if k == key:
                return v
        return default

    def all(self, key: str) -> list[str]:
        return [v for k, v in self.pairs if k == key]

    @property
    def classname(self) -> str:
        return self.get("classname")

    @property
    def targetname(self) -> str:
        return self.get("targetname")

    @property
    def origin(self) -> Vec3 | None:
        return parse_vec(self.get("origin"))

    def outputs(self) -> list[tuple[str, "Output"]]:
        """`(output name, parsed output)` for every keyvalue that parses as one."""
        found = []
        for k, v in self.pairs:
            parsed = Output.parse(v)
            if parsed is not None:
                found.append((k, parsed))
        return found

    def as_dict(self) -> dict[str, str]:
        return dict(self.pairs)


@dataclass(frozen=True)
class Output:
    """`target,input,parameter,delay,times`. Retail HL2 separates with commas."""

    target: str
    input: str
    parameter: str
    delay: float
    times: int

    @staticmethod
    def parse(value: str) -> "Output | None":
        separator = "\x1b" if "\x1b" in value else ","
        parts = value.split(separator)
        if len(parts) != 5:
            return None
        try:
            return Output(parts[0], parts[1], parts[2], float(parts[3]), int(parts[4]))
        except ValueError:
            return None


def parse_vec(raw: str) -> Vec3 | None:
    parts = raw.split()
    if len(parts) < 3:
        return None
    try:
        return (float(parts[0]), float(parts[1]), float(parts[2]))
    except ValueError:
        return None


def parse_entities(text: str) -> list[Entity]:
    """Tokenise `{ "key" "value" ... }` blocks. Values may hold braces."""
    entities: list[Entity] = []
    current: Entity | None = None
    pending_key: str | None = None
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == '"':
            end = text.find('"', i + 1)
            if end < 0:
                raise BspError("unterminated string in entity lump")
            token = text[i + 1:end]
            i = end + 1
            if current is None:
                raise BspError("keyvalue outside an entity block")
            if pending_key is None:
                pending_key = token
            else:
                current.pairs.append((pending_key, token))
                pending_key = None
            continue
        if c == "{":
            if current is not None:
                raise BspError("nested entity block")
            current = Entity()
        elif c == "}":
            if current is None or pending_key is not None:
                raise BspError("unbalanced entity block")
            entities.append(current)
            current = None
        i += 1
    if current is not None:
        raise BspError("entity lump ends inside a block")
    return entities


def load_map(bsp_path: Path) -> list[Entity]:
    return parse_entities(read_entity_lump(bsp_path))


def brush_model_bounds(bsp_path: Path) -> dict[str, tuple[Vec3, Vec3]]:
    """`*N` -> (mins, maxs) the compiler recorded for that brush model.

    The bounds are in the model's own space; a brush entity's world position is
    these plus its `origin` key (usually absent, meaning zero).
    """
    raw = read_lump(bsp_path, LUMP_MODELS)
    bounds: dict[str, tuple[Vec3, Vec3]] = {}
    for index in range(len(raw) // MODEL_STRUCT_SIZE):
        base = index * MODEL_STRUCT_SIZE
        mins = struct.unpack_from("<3f", raw, base)
        maxs = struct.unpack_from("<3f", raw, base + 12)
        bounds[f"*{index}"] = (mins, maxs)
    return bounds


def world_position(entity: Entity, bounds: dict[str, tuple[Vec3, Vec3]]) -> Vec3 | None:
    """Where an entity is: its origin, or for a brush entity its bounds centre."""
    model = entity.get("model")
    offset = entity.origin or (0.0, 0.0, 0.0)
    if model.startswith("*") and model in bounds:
        mins, maxs = bounds[model]
        return tuple((mins[i] + maxs[i]) / 2 + offset[i] for i in range(3))  # type: ignore[return-value]
    return entity.origin


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", type=Path, help="a .bsp file or a directory of them")
    parser.add_argument("--classname", action="append", default=[],
                        help="glob to filter classnames (repeatable)")
    parser.add_argument("--targetname", action="append", default=[],
                        help="glob to filter targetnames (repeatable)")
    parser.add_argument("--grep", action="append", default=[],
                        help="keep entities with this substring in any key or value "
                             "(case-insensitive, repeatable, OR'd)")
    parser.add_argument("--json", type=Path, help="write results as JSON to this path")
    parser.add_argument("--counts", action="store_true",
                        help="print per-map classname counts")
    parser.add_argument("--full", action="store_true",
                        help="keep every keyvalue rather than classname/targetname/origin")
    parser.add_argument("--raw", action="store_true",
                        help="print the entity lump verbatim; ignores every filter")
    args = parser.parse_args(argv)

    bsps = sorted(args.target.glob("*.bsp")) if args.target.is_dir() else [args.target]

    if args.raw:
        for bsp in bsps:
            if len(bsps) > 1:
                print(f"\n=== {bsp.stem} ===")
            print(read_entity_lump(bsp))
        return 0

    def globbed(value: str, patterns: list[str]) -> bool:
        return not patterns or any(fnmatch.fnmatch(value, p) for p in patterns)

    needles = [needle.lower() for needle in args.grep]

    def keep(entity: Entity) -> bool:
        if not globbed(entity.classname, args.classname):
            return False
        if not globbed(entity.targetname, args.targetname):
            return False
        if needles:
            blob = " ".join(f"{k} {v}" for k, v in entity.pairs).lower()
            return any(needle in blob for needle in needles)
        return True

    result: dict[str, list[dict[str, object]]] = {}
    for bsp in bsps:
        try:
            entities = load_map(bsp)
            bounds = brush_model_bounds(bsp)
        except BspError as exc:
            print(f"skipping {bsp.name}: {exc}", file=sys.stderr)
            continue
        kept: list[dict[str, object]] = []
        for entity in entities:
            if not keep(entity):
                continue
            position = world_position(entity, bounds)
            if args.full:
                kept.append({"pairs": entity.pairs, "position": position})
            else:
                kept.append({"classname": entity.classname,
                             "targetname": entity.targetname, "position": position})
        result[bsp.stem] = kept

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=1), encoding="utf-8")
        print(f"wrote {args.json} ({sum(len(v) for v in result.values())} entities)")
        return 0

    for map_name, entities in result.items():
        print(f"\n=== {map_name} ({len(entities)}) ===")
        if args.counts:
            counts: dict[str, int] = {}
            for entity in entities:
                counts[str(entity["classname"])] = counts.get(str(entity["classname"]), 0) + 1
            for classname, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
                print(f"  {count:4d}  {classname}")
        elif args.full:
            for entity in entities:
                pairs = entity["pairs"]
                print(f"\n  {dict(pairs).get('classname', '')}  @ {entity['position']}")
                for key, value in pairs:  # type: ignore[union-attr]
                    if key != "classname":
                        print(f"    {key:28} {value}")
        else:
            for entity in entities:
                print(f"  {entity['classname']:32} {entity['targetname']:24} "
                      f"{entity['position']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

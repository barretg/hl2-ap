"""Lookups the gameplay groups share. A leading underscore keeps this out of
the group registry (it exports no GROUP anyway)."""

from __future__ import annotations


def first(data, item: str) -> int:
    """The id of the "First <item>" check."""
    return data.location_named(f"First {item}").id


def source_at(data, item: str, map_name: str):
    """The source of "First <item>" on a map."""
    location = first(data, item)
    return next(s for s in data.sources if s.location == location and s.map == map_name)


def spawn_setup(source) -> list[str]:
    """Console setup that brings a templated copy into the world."""
    if not source.spawner:
        return []
    target, _, action = source.spawner.partition(",")
    return ["sv_cheats 1", f"ent_fire {target} {action}"]


def charger(data, map_prefix: str, classname: str):
    """The first charger check of a class on a map whose name starts so."""
    return next(l for l in data.locations.values()
                if l.kind == "charger" and l.map.startswith(map_prefix)
                and l.arg.startswith(classname + "@"))

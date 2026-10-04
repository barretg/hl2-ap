"""What a Source map's entity I/O says about which entities really exist.

Two facts the entity lump states only indirectly, both needed before an entity
can become a check:

- **Cold-load kits.** Nearly every HL2 map carries the player's expected
  loadout (suit, crowbar, guns) as `point_template` sources spawned from
  `logic_auto`'s `OnNewGame`, which fires only when the map is loaded directly
  (chapter select, `map`), never on a level transition. They are not pickups a
  playthrough meets, and counting them would put "First Crowbar" in every map.
- **Templates.** An entity named by a `point_template` does not exist when the
  map loads; it is removed and spawned later (or never) by `ForceSpawn`. One
  spawned in play is still a real source, at its template position.

Targetnames are case-insensitive in Source, and an output's target may end in
`*`; both are honoured.
"""

from __future__ import annotations

from collections import defaultdict
from fnmatch import fnmatchcase

from bsp_entities import Entity

# point_template: "Don't remove template entities" leaves the originals in the
# world as well as using them as a template.
SF_TEMPLATE_KEEP_ORIGINALS = 1


class MapLogic:
    def __init__(self, entities: list[Entity]) -> None:
        self.entities = entities
        self.by_name: dict[str, list[int]] = defaultdict(list)
        for index, entity in enumerate(entities):
            if entity.targetname:
                self.by_name[entity.targetname.lower()].append(index)
        # Template entity indices per point_template index.
        self.template_members: dict[int, list[int]] = {}
        for index, entity in enumerate(entities):
            if entity.classname != "point_template":
                continue
            members: list[int] = []
            for key, value in entity.pairs:
                if key.lower().startswith("template") and key[8:].isdigit():
                    members.extend(self.named(value))
            self.template_members[index] = members
        self.templated: set[int] = set()
        for index, members in self.template_members.items():
            spawnflags = int(entities[index].get("spawnflags", "0") or 0)
            if not spawnflags & SF_TEMPLATE_KEEP_ORIGINALS:
                self.templated.update(members)
        # Inputs each entity receives, `[(input lowercased, parameter)]`.
        self.received: dict[int, list[tuple[str, str]]] = defaultdict(list)
        for entity in entities:
            for _, parsed in entity.outputs():
                for index in self.named(parsed.target):
                    self.received[index].append((parsed.input.lower(), parsed.parameter))
        self.cold_load_only: set[int] = self._cold_load_only()

    def named(self, name: str) -> list[int]:
        name = name.lower()
        if name.endswith("*"):
            return [i for n, ids in self.by_name.items() if fnmatchcase(n, name)
                    for i in ids]
        return list(self.by_name.get(name, []))

    def _cold_load_only(self) -> set[int]:
        """Template members reachable from `OnNewGame` through relays,
        `env_entity_maker` and `point_template`."""
        queue: list[tuple[str, str]] = []
        for entity in self.entities:
            if entity.classname == "logic_auto":
                for output, parsed in entity.outputs():
                    if output.lower() == "onnewgame":
                        queue.append((parsed.target, parsed.input.lower()))
        spawned: set[int] = set()
        seen: set[tuple[str, str]] = set()
        while queue:
            target, input_name = queue.pop()
            if (target.lower(), input_name) in seen:
                continue
            seen.add((target.lower(), input_name))
            for index in self.named(target):
                entity = self.entities[index]
                classname = entity.classname
                if classname == "point_template" and input_name == "forcespawn":
                    spawned.update(self.template_members.get(index, []))
                elif classname == "env_entity_maker" and input_name == "forcespawn":
                    for template in self.named(entity.get("EntityTemplate")):
                        spawned.update(self.template_members.get(template, []))
                elif classname == "logic_relay" and input_name == "trigger":
                    for output, parsed in entity.outputs():
                        if output.lower() == "ontrigger":
                            queue.append((parsed.target, parsed.input.lower()))
        return spawned

    def exists_in_play(self, index: int) -> bool:
        """Will a playthrough arriving by transition ever meet this entity?"""
        return index not in self.cold_load_only

    def receives(self, index: int, input_name: str) -> list[str]:
        """The parameters of every `input_name` some output sends this entity."""
        return [p for i, p in self.received.get(index, []) if i == input_name.lower()]

    def inputs_to(self, classnames: set[str], input_name: str) -> list[int]:
        """Entities of these classes that some output sends `input_name` to."""
        return [index for index, entity in enumerate(self.entities)
                if entity.classname in classnames and self.receives(index, input_name)]

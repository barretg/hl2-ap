"""The scenario group registry: every module here exporting `GROUP`.

Adding a group is adding a file. Nothing else needs to change.
"""

from __future__ import annotations

import importlib
import pkgutil

from scenario import Context, Group, Scenario


def discover() -> dict[str, Group]:
    """`{name: group}` for every group module, sorted by name."""
    found: dict[str, Group] = {}
    for info in pkgutil.iter_modules(__path__):
        module = importlib.import_module(f"{__name__}.{info.name}")
        group = getattr(module, "GROUP", None)
        if not isinstance(group, Group):
            continue
        if group.name in found:
            raise ValueError(f"two groups named {group.name!r}")
        found[group.name] = group
    names = {alias: g.name for g in found.values() for alias in g.aliases}
    clash = set(names) & set(found)
    if clash:
        raise ValueError(f"group alias shadows a group: {sorted(clash)}")
    for group in found.values():
        for included in group.includes:
            if included not in found:
                raise ValueError(f"group {group.name!r} includes unknown {included!r}")
        _members(group.name, found, ())
    return dict(sorted(found.items()))


def _members(name: str, groups: dict[str, Group], path: tuple[str, ...]) -> list[str]:
    """`name` and every group it includes, depth first, each once."""
    if name in path:
        raise ValueError(f"groups include each other: {' -> '.join(path + (name,))}")
    order = [name]
    for included in groups[name].includes:
        for member in _members(included, groups, path + (name,)):
            if member not in order:
                order.append(member)
    return order


def needs_checkdata(name: str, groups: dict[str, Group]) -> bool:
    return any(groups[m].needs_checkdata for m in _members(name, groups, ()))


def build(name: str, groups: dict[str, Group], ctx: Context) -> list[Scenario]:
    """A group's scenarios followed by those of each group it includes.

    Each scenario carries its `origin`, the group its verdict is recorded
    under. A scenario reached twice (a subgroup that is a view of another)
    appears once, where it was first reached. Titles must be unique within
    one origin.
    """
    scenarios: list[Scenario] = []
    seen: set[tuple[str, str]] = set()
    for member in _members(name, groups, ()):
        own = groups[member].build(ctx)
        titles = [s.title for s in own]
        if len(set(titles)) != len(titles):
            raise ValueError(f"group {member} has duplicate scenario titles")
        for scenario in own:
            scenario.origin = scenario.origin or member
            key = (scenario.origin, scenario.title)
            if key not in seen:
                seen.add(key)
                scenarios.append(scenario)
    return scenarios


def canonical(name: str, groups: dict[str, Group]) -> str:
    """A group name with former names mapped to the current one."""
    for group in groups.values():
        if name in group.aliases:
            return group.name
    return name

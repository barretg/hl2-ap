"""The scenario group registry: every module here exporting `GROUP`.

Adding a group is adding a file. Nothing else needs to change.
"""

from __future__ import annotations

import importlib
import pkgutil

from scenario import Group


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
    return dict(sorted(found.items()))


def canonical(name: str, groups: dict[str, Group]) -> str:
    """A group name with former names mapped to the current one."""
    for group in groups.values():
        if name in group.aliases:
            return group.name
    return name

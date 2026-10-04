"""Assigns every test file to one subset (marker), so a change can be checked
with only the tests that cover it: `pytest -m install`. See pytest.ini.

A test file missing from SUBSETS fails collection, so no test silently falls
outside every subset.
"""

from __future__ import annotations

import pytest

SUBSETS = {
    "test_bridge.py": "bridge",
    "test_mod_install.py": "install",
    "test_aptest.py": "harness",
    "test_no_unreachable_code.py": "lint",
}


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        name = item.path.name
        if name not in SUBSETS:
            raise pytest.UsageError(f"{name} is in no test subset; add it to SUBSETS in tests/conftest.py")
        item.add_marker(SUBSETS[name])

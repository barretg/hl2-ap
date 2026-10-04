"""Loader for the generated campaign data.

`campaign.json` is produced by `tools/build_campaign_data.py` from the retail
maps. The world, the client and the game's `checkdata.txt` all read it, so a
location id is defined in exactly one place.
"""

from __future__ import annotations

import json
import pkgutil
from typing import Any

DATA_FILE = "campaign.json"


def load_campaign() -> dict[str, Any]:
    """`pkgutil.get_data`, not a file read: inside a zipped `.apworld`,
    `__file__` points into the archive and `open()` fails."""
    raw = pkgutil.get_data(__name__, DATA_FILE)
    if raw is None:
        raise FileNotFoundError(f"{__name__}/{DATA_FILE} is missing from the world package")
    return json.loads(raw.decode("utf-8"))


CAMPAIGN: dict[str, Any] = load_campaign()

DATA_VERSION: str = CAMPAIGN["data_version"]
CAMPAIGNS: list[dict[str, Any]] = CAMPAIGN["campaigns"]
CHAPTERS: list[dict[str, Any]] = CAMPAIGN["chapters"]
ITEMS: list[dict[str, Any]] = CAMPAIGN["items"]
LOCATIONS: list[dict[str, Any]] = CAMPAIGN["locations"]

CAMPAIGNS_BY_KEY: dict[str, dict[str, Any]] = {c["key"]: c for c in CAMPAIGNS}
CHAPTERS_BY_KEY: dict[str, dict[str, Any]] = {c["key"]: c for c in CHAPTERS}

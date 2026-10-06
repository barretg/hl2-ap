"""Regenerate `game/sdk.patch` and `game/sdk-compat.patch` from the SDK checkout.

Every file changed in `../source-sdk-2013` belongs to exactly one patch:
`HOOK_FILES` (behaviour: the hooks into our code, and what the retail game
needs of the client) go to `sdk.patch`, everything else (build fixes, no
behaviour change) to `sdk-compat.patch`. A file carrying both kinds (the
client's `clientmode_shared.cpp`) goes whole into `sdk.patch`, which applies
after compat. `--check` fails if either patch is stale.

Usage:
    python tools/sdk_patches.py [--check] [--sdk ../source-sdk-2013]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_SDK = REPO.parent / "source-sdk-2013"

HOOK_FILES = [
    "src/game/client/clientmode_shared.cpp",
    "src/game/client/hud_basechat.cpp",
    "src/game/server/EnvMessage.cpp",
    "src/game/server/ai_networkmanager.cpp",
    "src/game/server/client.cpp",
    "src/game/server/hl2/func_recharge.cpp",
    "src/game/server/hl2/hl2_player.cpp",
    "src/game/server/hl2/item_healthkit.cpp",
    "src/game/server/hl2/item_suit.cpp",
    "src/game/server/hl2/vehicle_airboat.cpp",
    "src/game/server/hl2/weapon_crowbar.h",
    "src/game/server/hl2/weapon_physcannon.cpp",
    "src/game/server/player.cpp",
    "src/game/server/triggers.cpp",
    "src/game/shared/basecombatweapon_shared.cpp",
    "src/tier1/KeyValues.cpp",
    "src/vgui2/vgui_controls/AnimationController.cpp",
]


def git(sdk: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(sdk), *args], check=True, capture_output=True,
                          text=True, encoding="latin-1").stdout


def build(sdk: Path) -> tuple[str, str]:
    changed = [line for line in git(sdk, "diff", "--name-only").splitlines() if line]
    hooks = [f for f in HOOK_FILES if f in changed]
    compat = sorted(set(changed) - set(HOOK_FILES))
    return (git(sdk, "diff", "--", *hooks) if hooks else "",
            git(sdk, "diff", "--", *compat) if compat else "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sdk", type=Path, default=DEFAULT_SDK)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    hooks, compat = build(args.sdk)
    targets = {REPO / "game" / "sdk.patch": hooks, REPO / "game" / "sdk-compat.patch": compat}
    stale = [p for p, text in targets.items()
             if not p.exists() or p.read_text(encoding="latin-1") != text]
    if args.check:
        for path in stale:
            print(f"stale: {path.relative_to(REPO)}")
        return 1 if stale else 0
    for path, text in targets.items():
        path.write_text(text, encoding="latin-1")
        print(f"wrote {path.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

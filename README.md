# Half-Life 2: Archipelago

An Archipelago randomizer for retail Half-Life 2 on Steam, the 20th anniversary
build. The campaign is cut into its 14 chapters, each locked behind a received
item; every weapon but the crowbar has to be found in the multiworld; and you
travel between chapters from a hub rather than playing straight through.

Player-facing docs: [setup guide](apworld/half_life_2/docs/setup_en.md)

This is the Source engine sibling of
[hl1-anniversary-ap](https://github.com/barretg/hl1-anniversary-ap), the same
design for Half-Life. The world, the client, the file bridge, the data
generators and the scenario harness are ported from it; what is new is the
chapter layout against Half-Life 2's own maps and the game side, which is a
Source SDK 2013 server and client dll.

**Status: feature complete for 0.1.0.** Every feature has passed its in-game
scenarios: chapters warp, checks fire, items arrive, pickups are refused until
the multiworld sends them, chapter exits return to the hub, Dark Energy's
credits send the goal, and DeathLink and the traps work. A full seed in a live
multiworld is the last step before release. See [game/README.md](game/README.md)
for how the game side is built and [docs/playtest.md](docs/playtest.md) for how
it is tested.

## The target

Retail Half-Life 2 on Steam, current build. Episode One and Episode Two are
planned for after 0.1.0.

The mod installs as a Steam sourcemod, `hl2ap`, so your Half-Life 2 install is
never written to and every map, model and sound is read from your own copy of
the game. It is plain HL2, not `hl2_complete`; [game/README.md](game/README.md)
says why. On Linux it runs under Proton.

## Chapters

14, from Point Insertion to Dark Energy, taken from the game's own chapter list:
the names are the `HL2_Chapter<n>_Title` strings in `hl2_english.txt`, and each
chapter's maps are found by walking its changelevels.

Dark Energy has no unlock item: it opens once `missions_required` other chapters
are finished, and its closing credits win the seed.

A chapter is entered from the hub with a fresh map load, so it is repeatable and
carries no state in from anywhere else. Transitions *inside* a chapter are the
game's own: inventory and level state carry exactly as retail does.

## The hub

New Game starts in `alpha_hub`, a map the mod ships (`maps/alpha_hub.vmf`,
compiled to the `.bsp` beside it), not on the train. Chapters are reached from
it with `!warp` or the `!menu` menu; a locked chapter says why.

Nothing in the hub can fire a check. The engine will not save on a map named
`background*`, and hub warp points are saves, so the hub cannot be one of the
game's menu backgrounds.

## Layout

```
apworld/half_life_2/       the Archipelago world
  data/campaign.json       generated: chapters, items, locations, logic groups
  data/ids.json            permanent item and location ids
  client/                  the AP client and the file bridge
  mod/                     the hl2ap sourcemod, plus its installer
    files/                 gameinfo.txt, checkdata.txt; the dlls and hub map
                           are added at packaging
  docs/                    setup guide and game page
game/                      the server and client dlls: sources, SDK patches,
                           build, and its own README
maps/                      the hub map's source and compiled .bsp
tools/                     generators, packaging, installer CLI
tests/                     bridge, data consistency and install tests
tests/aptest/              the in-game scenario harness
docs/protocol.md           the file bridge between client and game
docs/playtest.md           how a play-test session runs
build.py                   everything above, in order
```

## How the pieces fit

```
Archipelago server
      | AP protocol
Python client  (Launcher component)
      | text files in hl2ap/archipelago/
hl2ap server.dll and client.dll
      | SDK hooks (game/sdk.patch)
Half-Life 2 running d1_trainstation_01 ... d3_breen_01
```

The client is the source of truth; the game holds no state across map changes or
saves. See [docs/protocol.md](docs/protocol.md).

## Locations

169 in all:

| Type | Count | Fires when |
| --- | --- | --- |
| `map_reached` / `chapter_complete` | 68 / 14 | you reach a part of a chapter, or finish the chapter |
| `charger` | 74 | you press use on a health charger (41) or suit charger (33) |
| `weapon_pickup` | 11 | you first pick up that weapon |
| `item_pickup` / `weapon_upgrade` | 1 / 1 | the HEV suit; the super gravity gun |

Chargers fire on the `+use`, empty or not, so they are about finding one rather
than needing it. They can be switched off wholesale with `chargesanity: false`.
The game matches a use to the nearest charger of its class within 64 units.

A weapon check is the first copy of that weapon you pick up anywhere. Chapters
are played in any order, so logic gives each check **sources**: every chapter
part holding a copy, placed or dropped by an enemy, and the check is in logic
once any source is reachable. Copies nobody can reach are listed in
`unreachable_copies` in `tools/campaigns/hl2.py`, and the ones confirmed in play
in `confirmed_copies`.

Editorial decisions that *cannot* be derived from the maps (chapter names, which
classnames map to which item, and the logic gates) live in
[`tools/campaigns/hl2.py`](tools/campaigns/hl2.py). That is where to edit when
tuning logic.

Chapter keys there are permanent: `data/ids.json` keys every location by
chapter, so renaming one renumbers a location. Keys are the first map of the
chapter; names are free to change.

## Working on it

```bash
# everything: campaign data, check data, voice lines, SDK patches, both dll
# sets, the apworld, and a copy into /games/Archipelago/worlds
# (--worlds <folder> elsewhere, --no-install to only build)
python build.py

# after editing tools/campaigns/ alone
python tools/build_campaign_data.py
python tools/gen_checkdata.py

# the tests: this repo's and the world's (in ../Archipelago-src);
# --release adds Archipelago's general tests
python tools/run_tests.py

# install the hl2ap sourcemod without going through the Launcher
# (same code path as the client's /install); restart Steam after the first
python tools/install_mod.py
```

`campaign.json` and `checkdata.txt` are both committed, so neither the apworld
nor the client needs Half-Life 2 installed; only the generators do. The built
dlls and the hub `.bsp` are not in the world folder: `build_apworld.py` adds
them when it packages, and refuses to package without them unless given
`--allow-no-dll`. The dll build needs the Source SDK 2013 `singleplayer` branch
beside this checkout; [game/README.md](game/README.md) has the setup.

The hub is edited in Hammer: open `maps/alpha_hub.vmf`, compile, and keep the
`.bsp` next to it. `build.py` does not compile it.

### Checking logic in game

Anything the maps cannot prove (a copy out of bounds, a weapon only a scripted
scene hands over, a gate only an explosive clears) is confirmed by playing it.
`tests/aptest/aptest.py` stands in for the client and walks through scenarios
built from the installed `checkdata.txt`, in groups (`gating`, `travel`,
`traps`, `navigation` and the rest; `playtest` runs them all). It is driven
from the game, so once it is running the terminal can be left alone. It needs
the test build of the dlls, which `build.py` builds into `build/game-test`:

```bash
python tests/aptest/aptest.py --group playtest
```

The harness swaps the test dlls into the installed mod when it starts and puts
the release ones back when it stops. Start it before launching the game.

Then in game chat: `!next` loads the first untested scenario and puts you at
the spot; `!pass`, `!fail <what it needs>` or `!note <finding>` records a verdict
and loads the next. `!redo`, `!prev`, `!go <n>`, `!tp`, `!info`, `!list`,
`!give` and `!take` do what they say. Verdicts go to
`hl2ap/archipelago/aptest_results.txt`. [docs/playtest.md](docs/playtest.md)
has the full session.

## AI Usage Disclosure

Claude Code was used in the production of this apworld and client integrated into
the IDE. No images/assets or other such content were created with generative AI.
This apworld is fully human designed with no creative design input from
generative AI.

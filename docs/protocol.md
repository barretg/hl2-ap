# The file bridge

The Python client owns the connection to the Archipelago server; the game side is
a server dll with no networking of its own. The two talk through files in the mod
folder (`mod.install_sourcemod` returns where that is; under Proton it is the
library-side copy, see `apworld/half_life_2/mod/__init__.py`):

```
<mod folder>/archipelago/
    checkdata.txt   generated, read-only at runtime
    ap_in.txt       client -> game
    ap_out.txt      game -> client
    ap_amnesty.txt  game-owned, DeathLink amnesty remaining
```

Ported from the Half-Life 1 project, where every rule below was paid for with a
bug. `client/bridge.py` has no game or Archipelago dependency and is tested by
`tests/test_bridge.py`. The game side is stateless across map loads, which buys
save/load resilience for free.

Both sides poll every 0.2 s.

## Design rules

**The client is the source of truth.** The game must not gate on its cached copy
of a client-owned flag. `DEATH` is reported on every death and the client decides
whether it becomes a DeathLink; gating in the game let a stale snapshot swallow
deaths silently. DeathLink amnesty is the one exception, because the death
message names the remaining allowance at the instant of death: the client sends
the setting, the game counts down and tags the `DEATH` line, and the client still
decides whether anything leaves the slot.

**The game holds no state that matters across a map change.** On every map load
it re-reads `checkdata.txt` and waits for the next snapshot. A re-sent check is a
no-op on the server. `ap_amnesty.txt` is the one thing that must outlive a map
change.

**The snapshot is idempotent, events are not.** `ap_in.txt` is a complete
picture, safe to apply any number of times. Anything that must happen exactly
once (a filler grant, an incoming DeathLink) rides as a sequenced `event=` line.

**Events are acknowledged, not counted.** The game acts, writes `ACK|<seq>`, and
the client drops the line. The game needs no persistent cursor.

**The snapshot is written only when it changes**, never because `now=` moved.
Rewriting every poll with hundreds of pending filler items made the game reparse
and re-ACK them several times a second and starved the bridge.

**At most 16 events are in flight.** The rest wait in a backlog and drain as the
game acknowledges. Nothing is dropped. `DEATHLINK` and `CHAT` bypass the window.

## `ap_out.txt`, game to client

Append-only. The client keeps a byte cursor and consumes only complete lines. If
the file shrinks, the client treats it as a new game session and rewinds.

| Line | Meaning |
| --- | --- |
| `HELLO\|<map>` | the game started on this map; client replies with a forced snapshot |
| `CHECK\|<location id>` | a location was collected |
| `COMPLETE\|<chapter key>` | a mission was finished |
| `GOAL\|<chapter key>` | a game's finale was finished in play |
| `DEATH\|<player>\|<cause>\|<forgiven>` | the player died; `forgiven` is 1 when amnesty absorbed it. Never sent for a death the game dealt out to deliver a `DEATHLINK` |
| `CHAT\|<player>\|<message>` | in-game chat, for relaying to multiworld chat |
| `ACK\|<seq>` | event consumed |
| `APTEST\|<verb>\|<arg>` | test build only: a harness verb typed in game (section below) |

## `ap_in.txt`, client to game

A full snapshot, written to a temp file and renamed. The game reads it whole
every poll and early-outs if the text is byte-identical to the last parse. It
compares **content, never length**: `connected=1` and `connected=0` are the same
size.

```
session=9f3c1ab2
slot=Seed1234:3
data_version=d645439896ec
connected=1
death_link=1
death_link_amnesty=4
chapters=d1_canals_01,d1_trainstation_01
excluded=
items=Shotgun;Water Hazard Boat Keys
ungated=item_battery
starting=weapon_crowbar
checked=8000001,8000002
missing=8000003
gravity_gun_stage=2
melee_throw=1
now=1786000000
event=4|ITEM|Ammo Cache|1786000000
event=5|DEATHLINK|PlayerTwo~a hunter|1786000001
```

| Key | Meaning |
| --- | --- |
| `session` | one run of the client. Its event sequence restarts at 1 each launch, so on a change the game resets its high-water mark |
| `slot` | `<seed>:<slot>`: what says the run changed. On a change between two named slots the game returns to the hub. Empty means disconnected, not a new run |
| `data_version` | fingerprint of the id map. If it disagrees with `checkdata.txt` the game stops sending checks |
| `chapters` | open missions, comma separated. A game's finale is open when listed |
| `excluded` | missions not in this seed at all, so the game says "not in this seed" instead of "locked" |
| `items` | received item names, `;` separated (names may contain commas) |
| `ungated` | classnames the seed does not gate: neither granted nor refused |
| `starting` | classnames the run opens with and must never lose, in the seed's order. Empty means "use checkdata.txt", never "start with nothing" |
| `checked`, `missing` | location ids; between them they say which locations the seed contains, for the in-game tracker |
| other `key=value` | seed options the game acts on (`client.bridge` `options`), sorted; booleans as 1/0. New options need no protocol change; the game ignores keys it does not know |
| `now` | the client's clock. Event freshness compares an event's stamp to `now` from the same snapshot, so clocks never need to agree |

### Event lines

`event=<seq>|<kind>|<payload>|<unixtime>`

| Kind | Payload |
| --- | --- |
| `ITEM` | filler item name |
| `TRAP` | trap name, sprung once the level has settled |
| `DEATHLINK` | `<source>~<cause>` |
| `CHAT` | a line of multiworld chat to print in game |

Player names and chat are the only operator-controlled text; both sides strip `|`
and line breaks from them. Compound payloads join fields with `~`.

For two seconds after delivering a `DEATHLINK`, a death is the game's own: no
amnesty spent and no `DEATH` sent, or two slots trade deaths forever.
`death_link_amnesty` is the setting, not the countdown; the game keeps the
countdown in `ap_amnesty.txt` with the setting it came from, and resets it when
the setting changes.

## `checkdata.txt`

Generated from the same `campaign.json` the apworld reads, so ids cannot drift
between the halves. Pipe-delimited, one pass, no JSON parser, a format version
record first, additive evolution (older readers ignore new record types). The
record set is defined with the data pipeline (plan Phase 2).

## Scenario harness files (test build only)

`tests/aptest/aptest.py` stands in for the client and adds two files beside the
bridge. The release dll does not read them.

| File | Writer | Content |
| --- | --- | --- |
| `aptest_go.txt` | harness | `seq=`, `map=`, optional `pos=x y z`, optional `setup=<console command>` lines. The game loads the map when `seq` changes (never on first sight), waits until the player has been alive 1 s, teleports to a standing spot near `pos`, then runs each `setup` command |
| `aptest_say.txt` | harness, append-only | `hud\|text` shown on screen and in the console, `con\|text` console only. The game starts reading at the end, and holds output while a map loads |

Verbs typed in game as `!x` or `/x` in chat, or `ap_test x` in the console, go
back as `APTEST|x|arg`; `tp` alone is answered in game.

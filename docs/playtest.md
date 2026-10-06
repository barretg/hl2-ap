# Play-test runbook

Two halves. The harness half checks the game side scenario by scenario with
no server; the multiworld half checks the client and a real seed end to end.

## 1. Harness session

The harness stands in for the client, so close the real client first.

```sh
python tests/aptest/aptest.py --group playtest
```

Then launch **Half-Life 2 Archipelago**, open the console and type
`ap_test next`. `playtest` runs `phase5` (gating, checks, travel, deaths),
`phase6` (gravity gun, vehicles, logic) and `phase7` (melee, filler) in
turn; each is also a group of its own. Verbs as before: `!pass`, `!fail
<why>`, `!note <what>`, `!next` (the next scenario with no verdict, or one
failed in an earlier session), `!redo`, `!go <n>`, `!list`, `!item <name>`,
`!give`/`!take <item>`, `!deathlink`, `!connect`/`!disconnect`.

By default every item is held at every stage, so a scenario plays as retail
except for what it takes away (it says so when it starts).

The `logic` group is long play: each scenario asks whether a stretch can be
crossed without what logic says it needs. Skip any with `!next` and come back
to them.

Ctrl+C the harness when done; it puts the release dll back.

## 2. Multiworld session

Archipelago itself is yours to set up; nothing here installs into it.

1. Copy `build/half_life_2.apworld` into your Archipelago `custom_worlds`.
2. Generate with `docs/example.yaml` (alone, or with a friend's slot for
   DeathLink), and host the room.
3. Start the **Half-Life 2 Client** from the Launcher and connect. It finds
   the installed mod by itself (`/moddir` shows where).
4. Launch the game and start a New Game.

Check, in order:

| # | What | Expect |
|---|---|---|
| 1 | New Game | Point Insertion is excluded, so the hub loads; chat says `!ap` lists chapters |
| 2 | `!ap` in game, `/chapters` in the client | the same chapter statuses; one chapter unlocked |
| 3 | `!warp <that chapter>` | it loads fresh; Part 1 Reached shows in game and in the client |
| 4 | walk over a weapon you have not received | it stays put, the First check is sent |
| 5 | `/send` yourself an item from the server console (or wait for one) | `Received: X` in game; a weapon appears in your inventory |
| 6 | use a charger | its check in the client |
| 7 | finish the chapter | Complete check, back to the hub, the client counts it toward Dark Energy |
| 8 | close and restart the client mid-map | the game keeps your items; nothing is delivered twice |
| 9 | restart the game, load your save | back where you were; locked chapters still bounce you to the hub |
| 10 | filler from the server | Ammo Cache / Medkit / Battery act once, never again on reconnect |
| 11 | DeathLink (with two slots) | your death reaches the other slot after the amnesty runs out; theirs kills you |
| 12 | finish Dark Energy (or `/collect` and play the credits) | GOAL in the client, the slot shows as done, warp saves cleared |

Anything odd: the client log and `archipelago/ap_out.txt` / `ap_in.txt` in
the mod folder are the evidence; I can read them.

If the game freezes during a harness run, leave it frozen for 15 seconds before
killing it: the test build's watchdog then writes `archipelago/watchdog.txt`
(where it hung) and `watchdog.dmp`.

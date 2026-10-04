# hl2ap server.dll (installed as the `hl2ap` sourcemod)

The Source SDK 2013 `singleplayer` branch's `server_hl2` project (plain HL2, as
retail `hl2/bin/server.dll` ships), plus our sources in `src/`, built 32-bit with
clang-cl + lld-link + xwin from Linux.

## Build

```sh
git clone -b singleplayer https://github.com/ValveSoftware/source-sdk-2013.git ../source-sdk-2013
git -C ../source-sdk-2013 apply ../hl2-ap/game/sdk-compat.patch
git -C ../source-sdk-2013 apply ../hl2-ap/game/sdk.patch
cmake -S game -B build/game -G Ninja \
      -DCMAKE_TOOLCHAIN_FILE=$PWD/game/toolchain-clangcl-x86.cmake \
      -DSDK_DIR=../source-sdk-2013
cmake --build build/game
python tools/install_mod.py     # Steam sourcemods/hl2ap; restart Steam once
```

The toolchain path must be absolute (CMake resolves it against the build dir).

## Launching on Linux

Steam lists the mod as "Half-Life 2 Archipelago". Steam does not carry
Half-Life 2's compatibility setting over to a sourcemod entry, so the player
must set it once: Properties > Compatibility > force a Steam Play tool, and
pick Proton (Hotfix is what this project is tested with). Without it, launching
fails in Steam's UI with `Cannot read properties of null (reading
'display_name')`. Steam drops the setting whenever the entry is recreated (the
folder renamed or removed and reinstalled), so it has to be set again then.

## Not `hl2_complete`

The anniversary binaries special-case the `hl2_complete` game (merged
localization, the HL2/EP1/EP2 chapter list, per-campaign content switching),
but every one of them tests the literal `-game` command-line value, which for a
sourcemod is always a full path; and the content switching lives in Valve's
private `Release_hl2_complete` server code, absent from both public SDK
branches. So the mod is plain HL2. The episodes (Phase 9) need `server_episodic`
plus our own per-campaign switching.

## Why each piece

- **`singleplayer`, not `master`.** Retail HL2 is 32-bit and speaks
  ServerGameDLL009 / VEngineServer021 / ServerGameClients004. `master` is the
  64-bit multiplayer SDK and will not load.
- **Source lists come from Valve's `.vpc` scripts** via `tools/vpc_sources.py`,
  so nothing is hand-copied.
- **tier1 and mathlib are built from source**; the other static libs
  (choreoobjects, dmxloader, particles, tier2, tier3) are Valve's VS2013 builds,
  linked with `legacy_stdio_definitions`. tier0, vstdlib and steam_api are import
  libs; every symbol we import exists in the retail `bin/` dlls.
- **`sdk-compat.patch`** holds build fixes only (no behaviour changes):
  - `memoverride.cpp` taken from the SDK's `master` branch, which supports the
    VS2015+ UCRT; it still routes allocations to the retail tier0 allocator.
  - `RESTRICT` added to declarations whose definitions carry it (clang rejects
    the mismatch; MSVC ignored it). Mangling then matches Valve's prebuilt libs.
  - `SubFloat`/`SubInt` use the portable path: clang's `__m128` has no
    `m128_f32`.
  - 3DNow asm (`3dnow.cpp`, never selected on a modern CPU) and the unused
    naked `_SSE_VectorMA` are compiled out under clang.
  - One `COMPILE_TIME_ASSERT` on a pointer cast is skipped under clang.
  - `clientmode_shared.cpp`: a pointer compared `> 0` becomes `!= NULL`.
- **`/clang:-fno-delete-null-pointer-checks`** on all Valve code: it calls
  methods on null pointers (`KeyValues::deleteThis` on NULL) and relies on
  MSVC keeping the null test, which clang drops by default. Without it the
  client crashes setting up the HUD.
- **`compat/hypot_compat.cpp`** defines `_hypot` for the client: Valve's
  VS2013 `particles.lib` calls it, and taking it from the static UCRT also
  brings a second `hypot` that lld-link (unlike MSVC's linker) refuses.
- **The client links with `/SAFESEH:NO`**, as Valve's release scripts do:
  `vtf.lib`'s S3TC objects have no SafeSEH tables.
- **`compat/typeinfo.h`** shims a header the UCRT dropped.
- **`sdk.patch`** holds the hooks, one line each, kept apart from the build
  fixes. Most of the game side hangs off a `CAutoGameSystemPerFrame` in
  `src/ap_main.cpp` and needs no hook at all.
  - `game/server/client.cpp` `Host_Say` -> `ap::HandleChat`: `!x` and `/x` chat
    commands, and plain chat relayed to the client.
  - `tier1/KeyValues.cpp` `EvaluateConditional` and
    `vgui2/vgui_controls/AnimationController.cpp`: understand the 2025 retail
    scripts' `[$DECK]`/`[!$DECK]` conditionals (Steam Deck layouts; always
    false here). Without this every HUD element in `scripts/hudlayout.res`
    is dropped and the client crashes. `vgui_controls` is therefore built from
    source, not Valve's prebuilt lib.
  - `game/client/hud_basechat.cpp`: `hud_saytext_time` defaults to 30 s, so
    notices stay readable.
  - `game/server/hl2/hl2_player.cpp` `CHL2_Player::Spawn`: no longer sets
    `HIDEHUD_CHAT`, which hid the chat panel even once it could open.
  - `game/client/clientmode_shared.cpp` `StartMessageMode`: the "multiplayer
    only" early return removed, so chat opens in single player.

## The client

`client.dll` is built too, from `client_hl2.vpc`, and installed with the
server. The retail client refuses to open chat when `maxClients` is 1, and
chat is where `!` commands are typed; our own HUD elements will live here as
well. The two dlls come from the same SDK tree, so they always match. Its
exports and interface versions match retail `hl2/bin/client.dll`, apart from
Steam API interface versions (our SDK's headers are older; requested through
`VERSION_SAFE_STEAM_API_INTERFACES`) and retail's Workshop interface.

Apply it after `sdk-compat.patch`:
`git -C ../source-sdk-2013 apply ../hl2-ap/game/sdk.patch`.

## Test build

`-DHL2AP_TEST_BUILD=ON` compiles the scenario harness's game half
(`src/ap_aptest.cpp`, the `ap_test` command) in. Build it beside the release:

```sh
cmake -S game -B build/game-test -G Ninja \
      -DCMAKE_TOOLCHAIN_FILE=$PWD/game/toolchain-clangcl-x86.cmake \
      -DSDK_DIR=../source-sdk-2013 -DHL2AP_TEST_BUILD=ON
cmake --build build/game-test
```

`tests/aptest/aptest.py` swaps it into the installed mod while it runs and puts
the release dll back on exit. A release dll never contains the string `ap_test`.

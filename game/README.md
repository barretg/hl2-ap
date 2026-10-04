# hl2ap server.dll (installed as the `hl2ap` sourcemod)

The Source SDK 2013 `singleplayer` branch's `server_hl2` project (plain HL2, as
retail `hl2/bin/server.dll` ships), plus our sources in `src/`, built 32-bit with
clang-cl + lld-link + xwin from Linux.

## Build

```sh
git clone -b singleplayer https://github.com/ValveSoftware/source-sdk-2013.git ../source-sdk-2013
git -C ../source-sdk-2013 apply ../hl2-ap/game/sdk-compat.patch
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
- **`compat/typeinfo.h`** shims a header the UCRT dropped.
- Hooks for our features will live in a separate `sdk.patch`, kept small.

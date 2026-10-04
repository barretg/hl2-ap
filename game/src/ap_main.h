// Wiring, and the services every module uses.
//
// Source lets most of this hang off a game system (`CAutoGameSystemPerFrame`,
// see ap_main.cpp), so the SDK is patched only where nothing else reaches.
// Every hook is one line; `game/sdk.patch` applies them all and
// `game/README.md` says what each is for.
//
//   game/server/client.cpp   Host_Say   -> ap::HandleChat

#pragma once

#include <string>

class CBasePlayer;

namespace ap {

class Bridge;
struct PendingEvent;

// --- what the patched SDK files call -------------------------------------

// A chat line, before the engine shows it. True when it was ours (`!x` or
// `/x`) and must not be shown as chat.
bool HandleChat(CBasePlayer* player, const char* said);

// --- services ------------------------------------------------------------

// The single player. Null between map load and the player's spawn, which is
// most of what can go wrong in here, so every caller checks.
CBasePlayer* Player();

// The map the server is running.
std::string CurrentMap();

// `<mod folder>/archipelago`, where the bridge and the installed data live.
std::string StoreDir();

Bridge& Wire();

// Can the client take a user message yet? Frames run on this map since it
// loaded, and nothing the engine offers: HL1 found that every engine flag
// either is set before the load finishes or survives the load entirely, and
// a message written too early takes the game down. Everything that writes to
// the client waits on this.
bool ClientReady();

// Console text: the answer to a command the player typed. Lists go here and
// nowhere else.
void Say(const std::string& text);

// Something happened: a check was found, an item arrived, a pickup was
// refused. Printed to the console at once, and drawn on screen (top left, as
// HudMsg text: HL2's chat panel is laid out out of sight) where it is
// readable without opening the console.
//
// The screen part is queued: hooks run at moments a user message would crash
// the game (mid-load, inside a death). The frame loop draws it, redrawing at
// most four times a second so a burst cannot overrun the reliable channel.
void Notify(const std::string& text);

// Collect the answer to one command instead of sending it line by line. A
// short reply also goes on screen; a listing goes to the console only,
// with one line on screen saying where it went, so a bound key is never
// answered with nothing visible. `label` is the command as typed: `!status`.
void BeginReply(const std::string& label);
void EndReply();

// The longest reply that still goes on screen as well as the console.
constexpr size_t kReplyHudMaxLines = 9;

// Load a map from the frame loop. Hooks never change level inline; they ask
// for it here and the next frame does it.
void RequestMap(const std::string& map);

// Run a console command as the local player typed it, from the frame loop:
// commands like `kill` and `ch_createairboat` act on the command's client, and
// a command issued from the server has none. One per frame, in order.
void RequestPlayerCommand(const std::string& command);

// The poll clock, in real seconds rather than game time: the game time stops
// while the single-player game is paused, and the harness's console verbs are
// typed in exactly that state.
double Now();

// The bridge is checked this often rather than every frame; file I/O on every
// tick is waste and the client publishes far slower.
constexpr double kPollIntervalSeconds = 0.2;

// Where the bridge lives, relative to the mod folder.
extern const char* const kStoreSubdir;  // "archipelago"

}  // namespace ap

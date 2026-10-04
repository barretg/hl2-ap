#include "cbase.h"
#include "igamesystem.h"
#include "player.h"

#include "ap_aptest.h"

#include <cmath>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#include "ap_bridge.h"
#include "ap_main.h"
#include "ap_text.h"

// memdbgon must be the last include file in a .cpp file!!!
#include "tier0/memdbgon.h"

// triggers.cpp; it has no header.
bool IsTriggerClass(CBaseEntity* pEntity);

namespace ap {

#ifdef HL2AP_TEST_BUILD
namespace {

// How often the harness's files are looked at, in real seconds.
constexpr double kHarnessPollSeconds = 0.5;

// The scenario `aptest.py` last started, read from `aptest_go.txt`.
struct Destination {
    long seq = -1;
    std::string map;
    bool has_position = false;
    float position[3] = {0, 0, 0};
    std::vector<std::string> setup;
};

Destination g_destination;
// Whether the harness's files have been looked at since the dll loaded. What
// `aptest_go.txt` holds at that first look is a scenario from before the game
// started, and is only adopted: loading a map the moment the game starts would
// be a surprise, so `!redo` does that. Set on the first look whether or not
// the file is there yet, or the first scenario a fresh harness starts would be
// mistaken for an old one.
bool g_looked = false;
// Set when a scenario's map is requested, cleared once the player is placed.
bool g_arriving = false;
// When the player was first seen alive on the destination map, real seconds.
double g_alive_since = -1.0;
double g_next_poll = 0.0;
// How far into `aptest_say.txt` has been shown. It starts at the end, so a
// previous session's lines are not replayed.
std::streamoff g_say_cursor = -1;

std::string GoPath() { return StoreDir() + "/aptest_go.txt"; }
std::string SayPath() { return StoreDir() + "/aptest_say.txt"; }

bool ReadDestination(Destination& out) {
    std::ifstream file(GoPath().c_str());
    if (!file) {
        return false;
    }
    out = Destination();
    std::string line;
    while (std::getline(file, line)) {
        line = Trim(line);
        const size_t eq = line.find('=');
        if (eq == std::string::npos) {
            continue;
        }
        const std::string key = line.substr(0, eq);
        const std::string value = Trim(line.substr(eq + 1));
        if (key == "seq") {
            out.seq = ParseLong(value);
        } else if (key == "map") {
            out.map = value;
        } else if (key == "pos") {
            out.has_position = ParseVector(value, out.position);
        } else if (key == "setup" && !value.empty()) {
            out.setup.push_back(value);
        }
    }
    return !out.map.empty();
}

// Lines the harness wants shown: `hud|text` on screen (and in the
// console), `con|text` in the console only.
void ShowSaid() {
    std::ifstream file(SayPath().c_str(), std::ios::binary);
    if (!file) {
        return;
    }
    file.seekg(0, std::ios::end);
    const std::streamoff size = file.tellg();
    if (g_say_cursor < 0) {
        g_say_cursor = size;  // first look: skip what is already there
        return;
    }
    if (size < g_say_cursor) {
        g_say_cursor = 0;  // a new harness run truncated it
    }
    if (size == g_say_cursor) {
        return;
    }
    file.seekg(g_say_cursor);
    std::string chunk(static_cast<size_t>(size - g_say_cursor), '\0');
    file.read(&chunk[0], static_cast<std::streamsize>(chunk.size()));
    // Only whole lines; one being written is picked up next time.
    const size_t end = chunk.rfind('\n');
    if (end == std::string::npos) {
        return;
    }
    g_say_cursor += static_cast<std::streamoff>(end + 1);
    std::istringstream lines(chunk.substr(0, end + 1));
    std::string line;
    while (std::getline(lines, line)) {
        line = Trim(line);
        if (StartsWith(line, "hud|")) {
            Notify(line.substr(4));
        } else if (StartsWith(line, "con|")) {
            Say(line.substr(4));
        }
    }
}

void Load() {
    g_arriving = true;
    g_alive_since = -1.0;
    RequestMap(g_destination.map);
}

// Somewhere a standing player fits, as near the point as possible. Entity
// origins sit in lockers, on shelves and against walls, and dropping a player
// on the exact spot puts them in the geometry. Rings outward and upward, each
// spot checked with the player hull, then settled onto the floor.
//
// `strict` also wants the spot in sight of the point and floor beneath it:
// without that a free spot on the far side of a wall, or over the void outside
// the level, passes (sources harness, 2026-10-04).
bool StandSpot(CBasePlayer* player, const Vector& target, bool strict, Vector& out) {
    static const float kRadii[] = {0.0f, 24.0f, 48.0f, 80.0f, 128.0f};
    static const float kHeights[] = {36.0f, 72.0f, 0.0f, 128.0f};
    const Vector mins = player->GetPlayerMins();
    const Vector maxs = player->GetPlayerMaxs();
    for (float height : kHeights) {
        for (float radius : kRadii) {
            const int steps = radius == 0.0f ? 1 : 8;
            for (int i = 0; i < steps; ++i) {
                const float angle = 6.2831853f * i / steps;
                const Vector spot = target + Vector(radius * std::cos(angle),
                                                    radius * std::sin(angle), height);
                trace_t tr;
                UTIL_TraceHull(spot, spot, mins, maxs, MASK_PLAYERSOLID, player,
                               COLLISION_GROUP_PLAYER_MOVEMENT, &tr);
                if (tr.startsolid || tr.allsolid) {
                    continue;
                }
                if (strict) {
                    trace_t sight;
                    UTIL_TraceLine(target + Vector(0, 0, 8), spot, MASK_PLAYERSOLID_BRUSHONLY,
                                   player, COLLISION_GROUP_NONE, &sight);
                    if (sight.fraction < 1.0f && !sight.startsolid) {
                        continue;
                    }
                }
                UTIL_TraceHull(spot, spot - Vector(0, 0, 256), mins, maxs,
                               MASK_PLAYERSOLID, player,
                               COLLISION_GROUP_PLAYER_MOVEMENT, &tr);
                if (strict && tr.fraction >= 1.0f) {
                    continue;  // nothing to stand on
                }
                out = tr.endpos;
                return true;
            }
        }
    }
    return false;
}

void Teleport() {
    CBasePlayer* player = Player();
    if (player == nullptr || !player->IsAlive()) {
        return;
    }
    if (!g_destination.has_position) {
        return;  // the scenario starts where the map puts the player
    }
    if (player->IsInAVehicle()) {
        player->LeaveVehicle();
    }
    const Vector target(g_destination.position[0], g_destination.position[1],
                        g_destination.position[2]);
    Vector spot;
    if (!StandSpot(player, target, true, spot) && !StandSpot(player, target, false, spot)) {
        spot = target;
        Notify("[aptest] No room to stand near the spot; placed on it anyway.");
    }
    player->Teleport(&spot, nullptr, &vec3_origin);
}

// Everything but `tp` is the harness's to answer.
const char* const kHarnessVerbs[] = {
    "pass", "fail", "note", "next", "prev", "redo", "go", "info", "status",
    "list", "groups", "group", "give", "take", "item", "trap", "deathlink",
    "clear", "connect", "disconnect",
};

}  // namespace

bool TestBuild() { return true; }

// Trigger brushes ready to draw while the harness runs, hidden until the tester
// asks. `showtriggers` is read as each trigger spawns, so it is set before every
// map's entities are created (set directly, it needs no sv_cheats); then every
// trigger is hidden once the map is up. `showtriggers_toggle` (a cheat command,
// so `sv_cheats 1` first) flips them on and off from there.
class CShowTriggersSystem : public CAutoGameSystem {
public:
    CShowTriggersSystem() : CAutoGameSystem("CShowTriggersSystem") {}
    void LevelInitPreEntity() override {
        static ConVarRef showtriggers("showtriggers");
        if (showtriggers.IsValid()) {
            showtriggers.SetValue(1);
        }
    }
    void LevelInitPostEntity() override {
        for (CBaseEntity* entity = gEntList.FirstEnt(); entity;
             entity = gEntList.NextEnt(entity)) {
            if (IsTriggerClass(entity)) {
                entity->AddEffects(EF_NODRAW);
            }
        }
    }
};
CShowTriggersSystem g_show_triggers;

bool TestDispatch(const std::string& name, const std::string& rest) {
    if (name == "tp") {
        if (CurrentMap() != g_destination.map) {
            Notify("[aptest] Not on the scenario's map; !redo loads it.");
        } else {
            Teleport();
        }
        return true;
    }
    for (const char* verb : kHarnessVerbs) {
        if (name == verb) {
            Wire().Send("APTEST", std::vector<std::string>{name, Sanitise(rest)});
            return true;
        }
    }
    return false;
}

void RunTestHarness() {
    if (Now() >= g_next_poll) {
        g_next_poll = Now() + kHarnessPollSeconds;
        Destination next;
        const bool first = !g_looked;
        g_looked = true;
        if (ReadDestination(next) && next.seq != g_destination.seq) {
            g_destination = next;
            if (!first) {
                Load();
            }
        }
        // Held while a scenario's map loads: the load clears the screen,
        // and steps shown before it would be gone before they were read.
        if (!g_arriving) {
            ShowSaid();
        }
    }

    if (!g_arriving || CurrentMap() != g_destination.map) {
        return;
    }
    CBasePlayer* player = Player();
    if (player == nullptr || !player->IsAlive() || !ClientReady()) {
        g_alive_since = -1.0;
        return;
    }
    // A second after spawning, once the level's own spawn logic has run.
    if (g_alive_since < 0.0) {
        g_alive_since = Now();
        return;
    }
    if (Now() - g_alive_since < 1.0) {
        return;
    }
    g_arriving = false;
    Teleport();
    for (const std::string& command : g_destination.setup) {
        RequestPlayerCommand(command);
    }
    ShowSaid();
}

#else

bool TestBuild() { return false; }

bool TestDispatch(const std::string&, const std::string&) { return false; }

void RunTestHarness() {}

#endif

}  // namespace ap

#ifdef HL2AP_TEST_BUILD
// The console spelling of the harness verbs. Its name is also the marker
// `aptest.py` looks for to tell a test build from a release one.
CON_COMMAND(ap_test, "Scenario harness: ap_test pass|fail|note|next|prev|redo|go|info|"
                     "status|list|groups|group|give|take|item|trap|deathlink|clear|"
                     "connect|disconnect|tp")
{
    const std::string verb = ap::Lower(args.ArgC() > 1 ? args.Arg(1) : "");
    std::string rest;
    for (int i = 2; i < args.ArgC(); ++i) {
        rest += (rest.empty() ? "" : " ") + std::string(args.Arg(i));
    }
    if (!ap::TestDispatch(verb, rest)) {
        ap::Notify("[aptest] ap_test pass|fail|note|next|prev|redo|go|info|status|list|"
                   "groups|group|give|take|item|trap|deathlink|clear|connect|disconnect|tp");
    }
}
#endif

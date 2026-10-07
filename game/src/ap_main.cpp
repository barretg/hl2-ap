// The game side's spine: one game system that opens the bridge on every map
// load, polls it on its own clock, and runs everything a hook deferred.
//
// The rules are HL1's (`.claude/HL1_LEARNINGS.md` section 6), each paid for
// with a crash there: decide in the hook, act in the frame; nothing written to
// the client until frames have run on the map; a few lines per frame.

#include "cbase.h"
#include "igamesystem.h"
#include "player.h"

#include "ap_main.h"

#include <cstdio>
#include <deque>
#include <string>
#include <vector>

#include "ap_aptest.h"
#include "ap_bridge.h"
#include "ap_game.h"
#include "ap_melee.h"
#include "ap_state.h"
#include "ap_text.h"
#include "ap_nav.h"
#include "ap_traps.h"
#include "ap_watchdog.h"

// memdbgon must be the last include file in a .cpp file!!!
#include "tier0/memdbgon.h"

namespace ap {

const char* const kStoreSubdir = "archipelago";

namespace {

Bridge g_bridge;
bool g_started = false;
double g_next_poll = 0.0;

// Frames run since this map's LevelInitPostEntity. See `ClientReady`.
int g_frames_this_map = 0;
const int kFramesBeforeClientWrites = 3;

// Lines waiting for a frame safe enough to send them in. Large enough for a
// whole listing; capped only so a session that never gets a client cannot grow
// it for the life of the process. Oldest go first.
std::deque<std::string> g_notices;
const size_t kMaxHeldNotices = 512;

// Notices go to the chat panel as server chat (TextMsg, HUD_PRINTTALK); how
// long a line stays is the client's `hud_saytext_time`, 30 s in our client.
// A few lines per frame, as in HL1: each is a reliable user message.
const int kNoticesPerFrame = 4;
// One TextMsg must stay under the engine's 255-byte user message cap, and
// the chat panel is narrow, so long lines are wrapped at a space.
const size_t kChatWidth = 120;

void Queue(const std::string& text) {
    // The console always, at once: Msg is a local print and safe from any hook.
    Msg("[AP] %s\n", text.c_str());
    // Wrapped here so the per-frame budget counts what is actually sent.
    std::string rest = text;
    for (char& c : rest) {
        if (c == '\n' || c == '\r') {
            c = ' ';
        }
    }
    size_t indent = 0;
    while (!rest.empty()) {
        std::string piece;
        if (rest.size() > kChatWidth) {
            // Never cut inside the indent: that re-adds it forever.
            size_t cut = rest.rfind(' ', kChatWidth);
            if (cut == std::string::npos || cut <= indent) {
                cut = kChatWidth;
            }
            piece = rest.substr(0, cut);
            rest.erase(0, rest[cut] == ' ' ? cut + 1 : cut);
            rest.insert(0, "  ");  // continuation lines indented
            indent = 2;
        } else {
            piece.swap(rest);
        }
        g_notices.push_back(piece);
    }
    while (g_notices.size() > kMaxHeldNotices) {
        g_notices.pop_front();
    }
}

// The client formats a TextMsg with printf and looks up a leading '#' as a
// localisation token; neither belongs in a location name, but a name that
// silently vanished would be worse than an escaped one.
std::string ChatSafe(const std::string& text) {
    std::string out = "\x01";  // default chat colour
    if (!text.empty() && text[0] == '#') {
        out += ' ';
    }
    for (char c : text) {
        out += c;
        if (c == '%') {
            out += '%';
        }
    }
    return out + "\n";
}

void FlushNotices() {
    if (!ClientReady()) {
        return;  // held, not dropped: news across a quickload is worth showing
    }
    CBasePlayer* player = Player();
    for (int sent = 0; sent < kNoticesPerFrame && !g_notices.empty(); ++sent) {
        ClientPrint(player, HUD_PRINTTALK, ChatSafe(g_notices.front()).c_str());
        g_notices.pop_front();
    }
}

// The answer to the command being run right now. See `BeginReply`.
std::vector<std::string> g_reply;
bool g_collecting = false;
std::string g_reply_label;

std::string g_requested_map;
std::deque<std::string> g_player_commands;

void RunRequests() {
    if (!g_requested_map.empty()) {
        // `map`, not `changelevel`: a scenario or a warp starts the level fresh,
        // with no landmark and nothing carried over.
        const std::string command = "map " + g_requested_map + "\n";
        g_requested_map.clear();
        engine->ServerCommand(command.c_str());
        return;
    }
    if (!g_player_commands.empty() && ClientReady()) {
        CBasePlayer* player = Player();
        engine->ClientCommand(player->edict(), "%s\n", g_player_commands.front().c_str());
        g_player_commands.pop_front();
    }
}

void ApplyEvent(const PendingEvent& event) {
    if (event.kind == "CHAT") {
        Notify(event.payload);
    } else {
        // ITEM, TRAP and DEATHLINK. ACKed by the caller whatever happens:
        // holding one would stall the client's whole event window.
        GameEvent(event);
    }
}

void Poll() {
    if (Now() < g_next_poll) {
        return;
    }
    g_next_poll = Now() + kPollIntervalSeconds;

    std::vector<PendingEvent> events;
    if (!g_bridge.Poll(State(), events)) {
        return;
    }
    GameSnapshotChanged();
    for (const PendingEvent& event : events) {
        ApplyEvent(event);
        g_bridge.Acknowledge(event.seq);
    }
}

void Status() {
    const Snapshot& state = State();
    BeginReply("!status");
    Say("Map " + CurrentMap() + ", client " +
        (state.session.empty() ? std::string("not seen")
                               : state.connected ? std::string("connected")
                                                 : std::string("disconnected")));
    if (!state.slot.empty()) {
        Say("Slot " + state.slot + ", " + std::to_string(state.held_items.size()) +
            " items, " + std::to_string(state.checked.size()) + " checks sent");
    }
    GameStatus();
    EndReply();
}

void Help() {
    BeginReply("!help");
    Say("!status      where the client and this map stand");
    GameHelp();
    Say("!help        this list");
    if (TestBuild()) {
        Say("Test build: !pass !fail !note !next !prev !redo !go !info !list "
            "!groups !group !tp and more; !info in a scenario");
    }
    EndReply();
}

// Every `!x`. The harness's first in a test build, where it is the client.
bool Dispatch(const std::string& name, const std::string& rest) {
    WatchdogStage("Dispatch (chat or console command)");
    if (TestDispatch(name, rest)) {
        return true;
    }
    if (name == "status") {
        Status();
        return true;
    }
    if (name == "help") {
        Help();
        return true;
    }
    return GameDispatch(name, rest);
}

class CArchipelagoSystem : public CAutoGameSystemPerFrame {
public:
    CArchipelagoSystem() : CAutoGameSystemPerFrame("CArchipelagoSystem") {}

    void LevelInitPreEntity() override {
        WatchdogStage("LevelInitPreEntity");
        MeleePrecache();
        TrapsPrecache();
        NavPrecache();
        WatchdogStage("engine");
    }

    void LevelInitPostEntity() override {
        WatchdogStart(StoreDir().c_str());
        WatchdogStage("LevelInitPostEntity");
        g_bridge.Open(StoreDir());
        GameLevelStart();
        g_started = true;
        g_next_poll = 0.0;
        g_frames_this_map = 0;
        // Requests were for the level that just went away.
        g_requested_map.clear();
        g_player_commands.clear();
        // The client answers a HELLO with a forced snapshot, so this is what
        // gets our state back after any map load.
        g_bridge.Send("HELLO", CurrentMap());
        WatchdogStage("engine");
    }

    void LevelShutdownPreEntity() override { g_started = false; }

    void FrameUpdatePostEntityThink() override {
        WatchdogBeat();
        if (!g_started) {
            return;
        }
        if (g_frames_this_map < 1000) {
            ++g_frames_this_map;  // capped: only the first few are interesting
        }
        WatchdogStage("FlushNotices");
        FlushNotices();
        WatchdogStage("RunRequests");
        RunRequests();
        WatchdogStage("RunTestHarness");
        RunTestHarness();
        WatchdogStage("Poll");
        Poll();
        WatchdogStage("GameFrame");
        GameFrame();
        WatchdogStage("engine");
    }
};

CArchipelagoSystem g_system;

}  // namespace

CBasePlayer* Player() { return UTIL_GetLocalPlayer(); }

std::string CurrentMap() { return STRING(gpGlobals->mapname); }

std::string StoreDir() {
    // The full path of the mod folder as the engine resolved it, which under
    // Proton is the library-side copy (see apworld mod/__init__.py).
    char dir[MAX_PATH] = {0};
    engine->GetGameDir(dir, sizeof(dir));
    return std::string(dir) + "/" + kStoreSubdir;
}

Bridge& Wire() { return g_bridge; }

double Now() { return Plat_FloatTime(); }

bool ClientReady() {
    if (g_frames_this_map < kFramesBeforeClientWrites) {
        return false;
    }
    CBasePlayer* player = Player();
    return player != nullptr && player->IsConnected();
}

void Say(const std::string& text) {
    if (g_collecting) {
        g_reply.push_back(text);
        return;
    }
    // Msg is a local print, not a message to the client, so it is safe from
    // any hook and needs no queue.
    Msg("[AP] %s\n", text.c_str());
}

void Notify(const std::string& text) {
    if (g_collecting) {
        g_reply.push_back(text);
        return;
    }
    Queue(text);
}

void BeginReply(const std::string& label) {
    g_reply.clear();
    g_reply_label = label;
    g_collecting = true;
}

void EndReply() {
    g_collecting = false;
    const size_t lines = g_reply.size();
    if (lines > 0 && lines <= kReplyHudMaxLines) {
        for (const std::string& line : g_reply) {
            Queue(line);
        }
    } else {
        for (const std::string& line : g_reply) {
            Msg("[AP] %s\n", line.c_str());
        }
        char line[128];
        Q_snprintf(line, sizeof(line),
                   lines == 0 ? "%s: nothing to report." : "%s: %d lines in the console (~).",
                   g_reply_label.empty() ? "That command" : g_reply_label.c_str(),
                   static_cast<int>(lines));
        Queue(line);
    }
    g_reply.clear();
    g_reply_label.clear();
}

void RequestMap(const std::string& map) { g_requested_map = map; }

void RequestPlayerCommand(const std::string& command) {
    g_player_commands.push_back(command);
}

bool HandleChat(CBasePlayer* player, const char* said) {
    if (player == nullptr || said == nullptr) {
        return false;
    }
    // `say` hands the line over whole, often quoted.
    std::string text = Trim(said);
    if (text.size() >= 2 && text.front() == '"' && text.back() == '"') {
        text = Trim(text.substr(1, text.size() - 2));
    }
    if (text.empty()) {
        return false;
    }
    // A line starting with neither prefix is chat: it goes out to the
    // multiworld (the client decides whether to relay it) and the engine still
    // shows it here.
    if (text[0] != '!' && text[0] != '/') {
        g_bridge.Send("CHAT", std::vector<std::string>{Sanitise(player->GetPlayerName()),
                                                       Sanitise(text)});
        return false;
    }
    text.erase(text.begin());
    const size_t space = text.find_first_of(" \t");
    const std::string name = Lower(space == std::string::npos ? text : text.substr(0, space));
    const std::string rest =
        space == std::string::npos ? std::string() : Trim(text.substr(space + 1));
    if (!Dispatch(name, rest)) {
        // Ours to answer even when it is not a command we have: a player who
        // typed `!statsu` wants to be told, not to have it broadcast.
        Notify("No such command: !" + name + ". Try !help.");
    }
    return true;
}

}  // namespace ap

// The console spelling of every `!x`: `ap status`, `ap help`. Spelled out
// rather than CON_COMMAND, whose function would be named `ap` and collide with
// the namespace.
static void ApCommand(const CCommand& args)
{
    const std::string name = ap::Lower(args.ArgC() > 1 ? args.Arg(1) : "help");
    std::string rest;
    for (int i = 2; i < args.ArgC(); ++i) {
        rest += (rest.empty() ? "" : " ") + std::string(args.Arg(i));
    }
    if (!ap::Dispatch(name, rest)) {
        ap::Notify("No such command: ap " + name + ". Try ap help.");
    }
}

static ConCommand ap_command("ap", ApCommand, "Archipelago: ap help lists the commands");

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
#include "ap_state.h"
#include "ap_text.h"

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

// What is on screen. HL2's chat panel is laid out out of sight (and nothing
// typed into it reaches us), so notices are drawn as HudMsg text, the channel
// `game_text` uses, top left. Each line fades on its own clock.
struct BoardLine {
    std::string text;
    double expires;
};
std::deque<BoardLine> g_board;
// HudMsg has six channels; each carries a block of lines joined by newlines.
const int kBoardChannels = 6;
// One HudMsg must stay under the engine's 255-byte user message cap.
const size_t kMaxChannelBytes = 200;
// Lines are wrapped to this width, at a space where there is one.
const size_t kBoardWidth = 90;
const size_t kMaxBoardLines = 16;
const double kBoardHoldSeconds = 15.0;
// Redrawing sends one reliable message per channel, so it is rate limited:
// a burst of lines lands in one redraw rather than one per line.
const double kBoardRedrawSeconds = 0.25;
double g_next_redraw = 0.0;
bool g_board_dirty = false;
int g_channels_used = 0;

// The spacing between lines, as a fraction of the screen height. HudMsg's font
// depends on the resolution, so this is a cvar rather than a guess baked in.
ConVar ap_hud_line_height("ap_hud_line_height", "0.03", FCVAR_ARCHIVE,
                          "Archipelago: line spacing of on-screen notices, fraction of screen height");
ConVar ap_hud_y("ap_hud_y", "0.06", FCVAR_ARCHIVE,
                "Archipelago: top of the on-screen notices, fraction of screen height");

void Queue(const std::string& text) {
    // The console always, at once: Msg is a local print and safe from any hook.
    Msg("[AP] %s\n", text.c_str());
    g_notices.push_back(text);
    while (g_notices.size() > kMaxHeldNotices) {
        g_notices.pop_front();
    }
}

void AddToBoard(std::string text) {
    // A leading '#' would be looked up as a localisation token. Neither it nor
    // a newline belongs in a location name, but a name that silently vanished
    // would be worse than an ugly one.
    for (char& c : text) {
        if (c == '\n' || c == '\r') {
            c = ' ';
        }
    }
    const double expires = Now() + kBoardHoldSeconds;
    while (!text.empty()) {
        std::string piece;
        if (text.size() > kBoardWidth) {
            size_t cut = text.rfind(' ', kBoardWidth);
            if (cut == std::string::npos || cut == 0) {
                cut = kBoardWidth;
            }
            piece = text.substr(0, cut);
            text.erase(0, text[cut] == ' ' ? cut + 1 : cut);
            text.insert(0, "  ");  // continuation lines indented
        } else {
            piece.swap(text);
        }
        if (piece[0] == '#') {
            piece.insert(piece.begin(), ' ');
        }
        g_board.push_back(BoardLine{piece, expires});
    }
    while (g_board.size() > kMaxBoardLines) {
        g_board.pop_front();
    }
}

void DrawBoard() {
    CBasePlayer* player = Player();
    const double now = Now();
    const float line_height = ap_hud_line_height.GetFloat();
    float y = ap_hud_y.GetFloat();
    int channel = 0;
    size_t i = 0;
    while (i < g_board.size() && channel < kBoardChannels) {
        // A block of consecutive lines for one channel, held as long as its
        // newest line has left.
        std::string block;
        int lines = 0;
        double expires = now;
        while (i < g_board.size()) {
            const std::string& line = g_board[i].text;
            if (!block.empty() && block.size() + 1 + line.size() > kMaxChannelBytes) {
                break;
            }
            block += (block.empty() ? "" : "\n") + line;
            expires = g_board[i].expires;
            ++lines;
            ++i;
        }
        hudtextparms_t params = {};
        params.x = 0.02f;
        params.y = y;
        params.r1 = 255; params.g1 = 210; params.b1 = 120; params.a1 = 255;
        params.r2 = 255; params.g2 = 255; params.b2 = 255; params.a2 = 255;
        params.fadeoutTime = 0.5f;
        params.holdTime = static_cast<float>(expires - now);
        params.channel = channel;
        UTIL_HudMessage(player, params, block.c_str());
        y += line_height * lines;
        ++channel;
    }
    // Channels the board no longer needs still show what they last held.
    for (int unused = channel; unused < g_channels_used; ++unused) {
        hudtextparms_t params = {};
        params.holdTime = 0.01f;
        params.channel = unused;
        UTIL_HudMessage(player, params, " ");
    }
    g_channels_used = channel;
}

void FlushNotices() {
    // Lines whose time is up leave the board, and the rest move up.
    const double now = Now();
    while (!g_board.empty() && g_board.front().expires <= now) {
        g_board.pop_front();
        g_board_dirty = true;
    }
    if (!ClientReady()) {
        return;  // held, not dropped: news across a quickload is worth showing
    }
    if (!g_notices.empty()) {
        for (const std::string& text : g_notices) {
            AddToBoard(text);
        }
        g_notices.clear();
        g_board_dirty = true;
    }
    if (g_board_dirty && now >= g_next_redraw) {
        g_board_dirty = false;
        g_next_redraw = now + kBoardRedrawSeconds;
        DrawBoard();
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
        // ITEM, TRAP and DEATHLINK arrive with their features (plan Phases 5
        // and 7). ACKed anyway by the caller: holding one would stall the
        // client's whole event window.
        Msg("[AP] %s event not handled yet: %s\n", event.kind.c_str(),
            event.payload.c_str());
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
    EndReply();
}

void Help() {
    BeginReply("!help");
    Say("!status  where the client and this map stand");
    Say("!help    this list");
    if (TestBuild()) {
        Say("Test build: !pass !fail !note !next !prev !redo !go !info !list "
            "!groups !group !tp and more; !info in a scenario");
    }
    EndReply();
}

// Every `!x`. The harness's first in a test build, where it is the client.
bool Dispatch(const std::string& name, const std::string& rest) {
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
    return false;
}

class CArchipelagoSystem : public CAutoGameSystemPerFrame {
public:
    CArchipelagoSystem() : CAutoGameSystemPerFrame("CArchipelagoSystem") {}

    void LevelInitPostEntity() override {
        g_bridge.Open(StoreDir());
        g_started = true;
        g_next_poll = 0.0;
        g_frames_this_map = 0;
        // Requests were for the level that just went away.
        g_requested_map.clear();
        g_player_commands.clear();
        // The load cleared the client's HudMsg channels; whatever is still on
        // the board is drawn again once the client can take it.
        g_board_dirty = true;
        g_channels_used = 0;
        // The client answers a HELLO with a forced snapshot, so this is what
        // gets our state back after any map load.
        g_bridge.Send("HELLO", CurrentMap());
    }

    void LevelShutdownPreEntity() override { g_started = false; }

    void FrameUpdatePostEntityThink() override {
        if (!g_started) {
            return;
        }
        if (g_frames_this_map < 1000) {
            ++g_frames_this_map;  // capped: only the first few are interesting
        }
        FlushNotices();
        RunRequests();
        RunTestHarness();
        Poll();
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

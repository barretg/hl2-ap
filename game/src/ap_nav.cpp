#include "cbase.h"
#include "player.h"
#include "recipientfilter.h"
#include "ai_network.h"
#include "ai_node.h"
#include "ai_link.h"
#include "ai_hull.h"

#include <algorithm>
#include <cmath>
#include <functional>
#include <queue>
#include <vector>

#include "ap_nav.h"

#include "ap_checkdata.h"
#include "ap_game.h"
#include "ap_main.h"
#include "ap_state.h"
#include "ap_text.h"

// memdbgon must be the last include file in a .cpp file!!!
#include "tier0/memdbgon.h"

// Defined in te_beampoints.cpp; no SDK header declares it.
void TE_BeamPoints(IRecipientFilter& filter, float delay, const Vector* start, const Vector* end,
                   int modelindex, int haloindex, int startframe, int framerate, float life,
                   float width, float endWidth, int fadeLength, float amplitude, int r, int g,
                   int b, int a, int speed);

namespace ap {
namespace {

const char* const kBeamSprite = "sprites/laserbeam.vmt";
const int kItemsPerPage = 7;
const size_t kMenuChunk = 200;      // bytes per ShowMenu message
const size_t kMenuMax = 500;        // the client's whole menu string is 512
const size_t kLabelMax = 40;
const float kUnitsPerMetre = 39.37f;  // a unit is an inch
const float kVerticalWeight = 3.0f;   // climbing counts for more than walking
const float kTraceRefresh = 1.0f;     // seconds between beam redraws
const int kTraceMaxBeams = 30;

int g_beam_index = 0;

// --- targets ---------------------------------------------------------------------

struct Target {
    long id = 0;
    std::string name;
    Vector at;
};

// The changelevel trigger's destination, from its datamap: CChangeLevel is
// declared inside triggers.cpp, so its field is out of reach otherwise.
std::string ChangelevelMap(CBaseEntity* trigger) {
    for (datamap_t* map = trigger->GetDataDescMap(); map != nullptr; map = map->baseMap) {
        for (int i = 0; i < map->dataNumFields; ++i) {
            const typedescription_t& field = map->dataDesc[i];
            if (field.fieldName != nullptr && Q_strcmp(field.fieldName, "m_szMapName") == 0) {
                return reinterpret_cast<const char*>(trigger) +
                       field.fieldOffset[TD_OFFSET_NORMAL];
            }
        }
    }
    return std::string();
}

std::vector<Vector> ChangelevelsTo(const std::string& to) {
    std::vector<Vector> found;
    for (CBaseEntity* e = gEntList.FindEntityByClassname(nullptr, "trigger_changelevel");
         e != nullptr; e = gEntList.FindEntityByClassname(e, "trigger_changelevel")) {
        if (Lower(ChangelevelMap(e)) == Lower(to)) {
            found.push_back(e->WorldSpaceCenter());
        }
    }
    return found;
}

bool Missing(const Location& location) {
    return State().InSeed(location.id) && State().checked.count(location.id) == 0;
}

bool Matches(const Location& location, const std::string& filter) {
    return filter.empty() || Lower(location.name).find(Lower(filter)) != std::string::npos;
}

// "Suit Charger 1 (Part 2)" rather than "Route Kanal: Suit Charger 1 (Part 2)".
std::string ShortName(const std::string& name) {
    const size_t colon = name.find(": ");
    std::string text = colon == std::string::npos ? name : name.substr(colon + 2);
    if (text.size() > kLabelMax) {
        text = text.substr(0, kLabelMax - 3) + "...";
    }
    return text;
}

// Every place on this map where an unfound check matching `filter` can be had.
std::vector<Target> TargetsHere(const std::string& filter) {
    std::vector<Target> targets;
    const std::string map = CurrentMap();
    const Chapter* chapter = Data().ChapterOfMap(map);
    for (const Location& location : Data().Locations()) {
        if (!Missing(location) || !Matches(location, filter)) {
            continue;
        }
        auto add = [&](const Vector& at) { targets.push_back({location.id, location.name, at}); };
        if (location.has_position && location.map == map) {
            add(Vector(location.position[0], location.position[1], location.position[2]));
        }
        for (const Source& source : Data().Sources()) {
            if (source.location == location.id && source.map == map && source.has_position) {
                add(Vector(source.position[0], source.position[1], source.position[2]));
            }
        }
        if (location.type == "map_reached" && location.map != map) {
            for (const Vector& at : ChangelevelsTo(location.map)) {
                add(at);  // the way into the part it names
            }
        }
        if (location.type == "chapter_complete" && location.map == map && chapter != nullptr) {
            for (const auto& exit : chapter->exits) {
                if (exit.first == map) {
                    for (const Vector& at : ChangelevelsTo(exit.second)) {
                        add(at);
                    }
                }
            }
        }
    }
    return targets;
}

float WalkScore(const Vector& from, const Vector& to) {
    const Vector delta = to - from;
    return delta.Length2D() + kVerticalWeight * std::fabs(delta.z);
}

bool Nearest(CBasePlayer* player, const std::string& filter, Target& best) {
    bool any = false;
    float best_score = 0.0f;
    for (const Target& target : TargetsHere(filter)) {
        const float score = WalkScore(player->GetAbsOrigin(), target.at);
        if (!any || score < best_score) {
            best = target;
            best_score = score;
            any = true;
        }
    }
    return any;
}

std::string Metres(float units) {
    const int metres = static_cast<int>(units / kUnitsPerMetre + 0.5f);
    return std::to_string((std::max)(metres, 1)) + " m";
}

std::string Bearing(CBasePlayer* player, const Vector& at) {
    const Vector delta = at - player->GetAbsOrigin();
    const float yaw = UTIL_VecToYaw(delta);
    const float turn = UTIL_AngleDiff(yaw, player->EyeAngles().y);  // + is to the left
    const float a = std::fabs(turn);
    const char* side = turn > 0 ? "left" : "right";
    std::string where;
    if (a < 22.5f) {
        where = "ahead";
    } else if (a < 67.5f) {
        where = std::string("ahead to the ") + side;
    } else if (a < 112.5f) {
        where = std::string("to the ") + side;
    } else if (a < 157.5f) {
        where = std::string("behind to the ") + side;
    } else {
        where = "behind";
    }
    std::string text = Metres(delta.Length2D()) + " " + where;
    if (delta.z > 72.0f) {
        text += ", " + Metres(delta.z) + " up";
    } else if (delta.z < -72.0f) {
        text += ", " + Metres(-delta.z) + " down";
    }
    return text;
}

// Where else an unfound check can be had: the earliest open part with one,
// in chapter order, as a warp to suggest.
std::string Elsewhere(const std::string& filter) {
    for (const Chapter& chapter : Data().Chapters()) {
        if (!WarpOpen(chapter)) {
            continue;
        }
        for (size_t part = 0; part < chapter.maps.size(); ++part) {
            const std::string& map = chapter.maps[part];
            if (!PartOpen(chapter, static_cast<int>(part) + 1) || map == CurrentMap()) {
                continue;
            }
            for (const Location& location : Data().Locations()) {
                if (!Missing(location) || !Matches(location, filter)) {
                    continue;
                }
                bool here = location.map == map && location.type != "map_reached";
                for (const Source& source : Data().Sources()) {
                    here = here || (source.location == location.id && source.map == map);
                }
                if (here) {
                    return location.name + ": !warp " + chapter.number + " " +
                           std::to_string(part + 1);
                }
            }
        }
    }
    return std::string();
}

// --- trace -----------------------------------------------------------------------

bool g_tracing = false;
Target g_trace;
float g_next_beam = 0.0f;

// The ground node nearest `at` that it can see, else the nearest at all.
// Not CAI_Network::NearestNodeToPoint: its visibility check traces with a
// filter built on the asking NPC, and with none it crashed the game.
int NearestNode(CAI_Network* net, const Vector& at) {
    const int kCandidates = 8;
    std::vector<std::pair<float, int>> nearest;
    for (int id = 0; id < net->NumNodes(); ++id) {
        CAI_Node* node = net->GetNode(id, false);
        if (node == nullptr || node->GetType() != NODE_GROUND) {
            continue;
        }
        nearest.emplace_back((node->GetOrigin() - at).LengthSqr(), id);
    }
    if (nearest.empty()) {
        return NO_NODE;
    }
    const size_t keep = (std::min)(nearest.size(), static_cast<size_t>(kCandidates));
    std::partial_sort(nearest.begin(), nearest.begin() + keep, nearest.end());
    const Vector lift(0, 0, 16);
    for (size_t i = 0; i < keep; ++i) {
        trace_t tr;
        UTIL_TraceLine(at + lift, net->GetNode(nearest[i].second, false)->GetOrigin() + lift,
                       MASK_SOLID_BRUSHONLY, nullptr, COLLISION_GROUP_NONE, &tr);
        if (tr.fraction >= 1.0f) {
            return nearest[i].second;
        }
    }
    return nearest.front().second;
}

// Node path from near `from` to near `to` over the AI node graph, walkable by
// a human hull. Empty when there is no graph or no way.
std::vector<Vector> NodePath(const Vector& from, const Vector& to) {
    std::vector<Vector> path;
    CAI_Network* net = g_pBigAINet;
    if (net == nullptr || net->NumNodes() == 0) {
        return path;
    }
    const int start = NearestNode(net, from);
    const int goal = NearestNode(net, to);
    if (start == NO_NODE || goal == NO_NODE) {
        return path;
    }
    const int count = net->NumNodes();
    std::vector<float> cost(count, FLT_MAX);
    std::vector<int> previous(count, NO_NODE);
    using Entry = std::pair<float, int>;
    std::priority_queue<Entry, std::vector<Entry>, std::greater<Entry>> open;
    cost[start] = 0.0f;
    open.push({0.0f, start});
    while (!open.empty()) {
        const Entry top = open.top();
        open.pop();
        const int id = top.second;
        if (id == goal) {
            break;
        }
        if (top.first > cost[id]) {
            continue;
        }
        CAI_Node* node = net->GetNode(id, false);
        if (node == nullptr) {
            continue;
        }
        for (int i = 0; i < node->NumLinks(); ++i) {
            CAI_Link* link = node->GetLinkByIndex(i);
            if (link == nullptr || (link->m_LinkInfo & bits_LINK_OFF) ||
                link->m_iAcceptedMoveTypes[HULL_HUMAN] == 0) {
                continue;
            }
            const int next = link->DestNodeID(id);
            CAI_Node* other = net->GetNode(next, false);
            if (other == nullptr) {
                continue;
            }
            const float step = cost[id] + WalkScore(node->GetOrigin(), other->GetOrigin());
            if (step < cost[next]) {
                cost[next] = step;
                previous[next] = id;
                open.push({step, next});
            }
        }
    }
    if (cost[goal] == FLT_MAX) {
        return path;
    }
    for (int id = goal; id != NO_NODE; id = previous[id]) {
        path.push_back(net->GetNode(id, false)->GetOrigin());
    }
    std::reverse(path.begin(), path.end());
    return path;
}

void Beam(CBasePlayer* player, const Vector& a, const Vector& b) {
    CSingleUserRecipientFilter filter(player);
    const Vector lift(0, 0, 16);
    const Vector from = a + lift;
    const Vector to = b + lift;
    TE_BeamPoints(filter, 0.0f, &from, &to, g_beam_index, 0, 0, 0, kTraceRefresh + 0.15f, 4.0f,
                  4.0f, 0, 0.0f, 255, 160, 0, 200, 0);
}

void DrawTrace(CBasePlayer* player) {
    std::vector<Vector> points{player->GetAbsOrigin()};
    for (const Vector& node : NodePath(player->GetAbsOrigin(), g_trace.at)) {
        points.push_back(node);
    }
    points.push_back(g_trace.at);
    for (size_t i = 0; i + 1 < points.size() && static_cast<int>(i) < kTraceMaxBeams; ++i) {
        Beam(player, points[i], points[i + 1]);
    }
}

void StopTrace(const std::string& why) {
    if (g_tracing) {
        g_tracing = false;
        if (!why.empty()) {
            Notify(why);
        }
    }
}

void Find(const std::string& filter) {
    CBasePlayer* player = Player();
    if (player == nullptr) {
        return;
    }
    Target best;
    if (Nearest(player, filter, best)) {
        Notify(ShortName(best.name) + ": " + Bearing(player, best.at) + ". !trace shows the way.");
        return;
    }
    const std::string other = Elsewhere(filter);
    Notify(other.empty() ? std::string("No unfound check") +
                               (filter.empty() ? "" : " matching \"" + filter + "\"") +
                               " anywhere you can warp to."
                         : "None on this map. Nearest open: " + other);
}

void Trace(const std::string& filter, long only_id = 0) {
    CBasePlayer* player = Player();
    if (player == nullptr) {
        return;
    }
    if (g_tracing && filter.empty() && only_id == 0) {
        StopTrace("");  // the line going away is the answer, as in HL1
        return;
    }
    Target best;
    bool found = false;
    if (only_id != 0) {
        float best_score = 0.0f;
        for (const Target& target : TargetsHere("")) {
            const float score = WalkScore(player->GetAbsOrigin(), target.at);
            if (target.id == only_id && (!found || score < best_score)) {
                best = target;
                best_score = score;
                found = true;
            }
        }
    } else {
        found = Nearest(player, filter, best);
    }
    if (!found) {
        Find(filter);  // says where else, if anywhere
        return;
    }
    g_tracing = true;
    g_trace = best;
    g_next_beam = 0.0f;
    Notify("Tracing to " + ShortName(best.name) + ": " + Bearing(player, best.at) +
           ". !trace again to stop.");
}

// --- tracker ---------------------------------------------------------------------

// The key of the chapter the tracker shows; empty follows wherever the player
// is. A key, not a pointer: the check data is reloaded with every map.
std::string g_tracked;

bool IsWeaponCheck(const Location& location) {
    return location.type == "weapon_pickup" || location.type == "item_pickup" ||
           location.type == "weapon_upgrade";
}

// A part's own checks: everything on its map but the weapons, which can be
// had wherever that weapon is and are listed apart.
std::vector<const Location*> PartChecks(const Chapter& chapter, int part) {
    std::vector<const Location*> checks;
    for (const Location& location : Data().Locations()) {
        if (location.map == chapter.maps[part - 1] && !IsWeaponCheck(location) &&
            State().InSeed(location.id)) {
            checks.push_back(&location);
        }
    }
    return checks;
}

std::vector<const Location*> WeaponChecks() {
    std::vector<const Location*> checks;
    for (const Location& location : Data().Locations()) {
        if (IsWeaponCheck(location) && State().InSeed(location.id)) {
            checks.push_back(&location);
        }
    }
    return checks;
}

std::string Count(const std::vector<const Location*>& checks) {
    int found = 0;
    for (const Location* location : checks) {
        found += State().checked.count(location->id) != 0 ? 1 : 0;
    }
    return std::to_string(found) + "/" + std::to_string(checks.size());
}

std::string ItemsLine() {
    int weapons = 0;
    int weapons_held = 0;
    for (const auto& gate : Data().Gates()) {
        if (gate.first.compare(0, 7, "weapon_") == 0) {
            ++weapons;
            weapons_held += HeldItem(gate.second) ? 1 : 0;
        }
    }
    int keys = 0;
    int keys_held = 0;
    for (const Chapter& c : Data().Chapters()) {
        const VehicleKey* key = Data().KeyFor(c.key);
        if (key != nullptr && !State().ChapterExcluded(c.key)) {
            ++keys;
            keys_held += HeldItem(key->item) ? 1 : 0;
        }
    }
    return "Weapons held " + std::to_string(weapons_held) + "/" + std::to_string(weapons) +
           ", keys " + std::to_string(keys_held) + "/" + std::to_string(keys);
}

const Chapter* TrackedChapter() {
    const Chapter* tracked = g_tracked.empty() ? nullptr : Data().ChapterByKey(g_tracked);
    return tracked != nullptr ? tracked : Data().ChapterOfMap(CurrentMap());
}

// The chapter and part (1-based) a map is, or null.
const Chapter* PartOf(const std::string& map, int& part) {
    const Chapter* chapter = Data().ChapterOfMap(map);
    if (chapter != nullptr) {
        const auto at = std::find(chapter->maps.begin(), chapter->maps.end(), map);
        part = static_cast<int>(at - chapter->maps.begin()) + 1;
    }
    return chapter;
}

// How to get to a part from here, as a warp or the reason there is none.
std::string WayTo(const std::string& map) {
    int part = 0;
    const Chapter* chapter = PartOf(map, part);
    if (chapter == nullptr) {
        return "outside any chapter";
    }
    const std::string where = chapter->name + " part " + std::to_string(part);
    if (!WarpOpen(*chapter)) {
        return where + " (" + ChapterStatusText(*chapter) + ")";
    }
    if (!PartOpen(*chapter, part)) {
        return where + " (not reached yet: !warp " + chapter->number + ")";
    }
    return where + ": !warp " + chapter->number + (part > 1 ? " " + std::to_string(part) : "");
}

// A check picked in the tracker: found already, traced if it is on this map,
// else which part it is in and the warp there.
void Describe(long id) {
    const Location* location = Data().LocationById(id);
    if (location == nullptr) {
        return;
    }
    const std::string name = ShortName(location->name);
    if (State().checked.count(id) != 0) {
        Notify(name + ": already found.");
        return;
    }
    for (const Target& target : TargetsHere("")) {
        if (target.id == id) {
            Trace("", id);
            return;
        }
    }
    if (!IsWeaponCheck(*location)) {
        Notify(name + ": " + WayTo(location->map) + ".");
        return;
    }
    // A weapon: the earliest open part with one, in chapter order.
    for (const Chapter& chapter : Data().Chapters()) {
        for (const std::string& map : chapter.maps) {
            for (const Source& source : Data().Sources()) {
                int part = 0;
                if (source.location == id && source.map == map && PartOf(map, part) &&
                    WarpOpen(chapter) && PartOpen(chapter, part)) {
                    Notify(name + ": " + WayTo(map) + ".");
                    return;
                }
            }
        }
    }
    Notify(name + ": first in " + WayTo(location->map) + "; nowhere open has one yet.");
}

// The tracker in the console, laid out as HL1's: a heading per part with its
// count, a [x]/[ ] line per check, the weapons apart, the seed's total last.
// A filter keeps a part whose chapter or map matches whole, and otherwise only
// the checks whose names match; the total stays the seed's.
void ConsoleTracker(const std::string& filter) {
    if (State().checked.empty() && State().missing.empty()) {
        Say("No location data yet. Is the client connected?");
        return;
    }
    const std::string wanted = Simplify(filter);
    auto hit = [&](const std::string& text) {
        return !wanted.empty() && Simplify(text).find(wanted) != std::string::npos;
    };
    auto mark = [](const Location* location) {
        return std::string("    ") + (State().checked.count(location->id) != 0 ? "[x] " : "[ ] ") +
               location->name;
    };

    Say("=== Archipelago: location tracker ===");
    int found = 0;
    int total = 0;
    int shown = 0;
    auto section = [&](const std::string& head, const std::vector<const Location*>& checks,
                       bool whole) {
        for (const Location* location : checks) {
            found += State().checked.count(location->id) != 0 ? 1 : 0;
        }
        total += static_cast<int>(checks.size());
        std::vector<const Location*> listed;
        for (const Location* location : checks) {
            if (wanted.empty() || whole || hit(location->name)) {
                listed.push_back(location);
            }
        }
        if (listed.empty()) {
            return;
        }
        ++shown;
        Say(head + "  (" + Count(checks) + ")");
        for (const Location* location : listed) {
            Say(mark(location));
        }
    };

    for (const Chapter& chapter : Data().Chapters()) {
        if (State().ChapterExcluded(chapter.key)) {
            continue;
        }
        for (size_t part = 0; part < chapter.maps.size(); ++part) {
            const std::vector<const Location*> checks =
                PartChecks(chapter, static_cast<int>(part) + 1);
            if (checks.empty()) {
                continue;
            }
            const std::string& map = chapter.maps[part];
            const std::string head =
                chapter.maps.size() > 1
                    ? chapter.name + ", part " + std::to_string(part + 1) + " -- " + map
                    : chapter.name + " -- " + map;
            section(head, checks, hit(chapter.name) || hit(map));
        }
    }
    const std::vector<const Location*> weapons = WeaponChecks();
    if (!weapons.empty()) {
        section("Half-Life 2: Weapons", weapons, hit("Half-Life 2 weapons"));
    }

    if (shown == 0 && !wanted.empty()) {
        Say("Nothing matches \"" + filter + "\".");
    }
    Say("Found " + std::to_string(found) + " of " + std::to_string(total) +
        " locations in this seed.");
}

// --- menu ------------------------------------------------------------------------

struct Entry {
    std::string label;
    std::function<void()> act;
};

enum class Page {
    kNone, kMain, kChapters, kParts, kWarpPoints,
    kTracker,          // the tracked chapter: its parts, weapons, other chapters
    kTrackChapters,    // every chapter in the seed, to track another
    kTrackChecks,      // one part's checks, or the weapons
};

Page g_page = Page::kNone;
int g_first = 0;               // index of the first entry shown
const Chapter* g_parts_of = nullptr;
// What kTrackChecks lists: a part of g_tracked (1-based), or 0 for the weapons.
int g_track_part = 0;
int g_selected = 0;            // a pick waiting for the next frame

void Open(Page page, int first = 0);

void Send(CBasePlayer* player, int valid, const std::string& text) {
    CSingleUserRecipientFilter filter(player);
    filter.MakeReliable();
    if (valid == 0 || text.empty()) {
        UserMessageBegin(filter, "ShowMenu");
        WRITE_SHORT(0);
        WRITE_CHAR(0);
        WRITE_BYTE(0);
        WRITE_STRING("");
        MessageEnd();
        return;
    }
    for (size_t at = 0; at < text.size(); at += kMenuChunk) {
        const bool more = at + kMenuChunk < text.size();
        UserMessageBegin(filter, "ShowMenu");
        WRITE_SHORT(valid);
        WRITE_CHAR(-1);  // stays until a key is pressed
        WRITE_BYTE(more ? 1 : 0);
        WRITE_STRING(text.substr(at, kMenuChunk).c_str());
        MessageEnd();
    }
}

std::vector<Entry> g_entries;
std::string g_header;

void Show() {
    CBasePlayer* player = Player();
    if (player == nullptr || !ClientReady()) {
        return;
    }
    std::string text = g_header + "\n\n";
    int valid = 1 << 9;  // 0, exit
    const int count = static_cast<int>(g_entries.size());
    for (int i = 0; i < kItemsPerPage && g_first + i < count; ++i) {
        text += std::to_string(i + 1) + ". " + g_entries[g_first + i].label + "\n";
        valid |= 1 << i;
    }
    text += "\n";
    if (g_first > 0 || g_page != Page::kMain) {
        text += "8. Back\n";
        valid |= 1 << 7;
    }
    if (g_first + kItemsPerPage < count) {
        text += "9. More\n";
        valid |= 1 << 8;
    }
    text += "0. Exit";
    if (text.size() > kMenuMax) {
        text = text.substr(0, kMenuMax);
    }
    Send(player, valid, text);
}

void Close() {
    g_page = Page::kNone;
    if (CBasePlayer* player = Player()) {
        if (ClientReady()) {
            Send(player, 0, "");
        }
    }
}

std::string PartLabel(const Chapter& chapter, int part) {
    int found = 0;
    int total = 0;
    for (const Location& location : Data().Locations()) {
        if (location.map == chapter.maps[part - 1] && State().InSeed(location.id)) {
            ++total;
            found += State().checked.count(location.id) != 0 ? 1 : 0;
        }
    }
    return std::to_string(found) + "/" + std::to_string(total);
}

void Build(Page page) {
    g_entries.clear();
    switch (page) {
        case Page::kMain:
            g_header = "Archipelago";
            g_entries.push_back({"Warp to a chapter", [] { Open(Page::kChapters); }});
            g_entries.push_back({"Warp points", [] { Open(Page::kWarpPoints); }});
            g_entries.push_back({"Tracker", [] {
                                     Open(Page::kTracker);
                                 }});
            g_entries.push_back({"Find the nearest check", [] { Find(""); }});
            g_entries.push_back({g_tracing ? "Stop tracing" : "Trace to the nearest check",
                                 [] { Trace(""); }});
            g_entries.push_back({"Go to the hub", [] { GameDispatch("hub", ""); }});
            g_entries.push_back({"Set this part's warp point", [] { GameDispatch("setwarp", ""); }});
            break;
        case Page::kChapters:
            g_header = "Warp to a chapter";
            for (const Chapter& chapter : Data().Chapters()) {
                if (!WarpOpen(chapter)) {
                    continue;
                }
                const Chapter* c = &chapter;
                g_entries.push_back({chapter.number + ". " + chapter.name + " [" +
                                         ChapterStatusText(chapter) + "]",
                                     [c] {
                                         int reached = 0;
                                         for (size_t p = 1; p <= c->maps.size(); ++p) {
                                             reached += PartOpen(*c, static_cast<int>(p)) ? 1 : 0;
                                         }
                                         if (reached <= 1) {
                                             GameDispatch("warp", c->number);
                                         } else {
                                             g_parts_of = c;
                                             Open(Page::kParts);
                                         }
                                     }});
            }
            if (g_entries.empty()) {
                g_header += "\n(nothing open yet)";
            }
            break;
        case Page::kParts: {
            const Chapter* c = g_parts_of;
            if (c == nullptr) {
                break;
            }
            g_header = c->name;
            g_entries.push_back({"From the start", [c] { GameDispatch("warp", c->number); }});
            for (size_t p = 1; p <= c->maps.size(); ++p) {
                const int part = static_cast<int>(p);
                if (!PartOpen(*c, part)) {
                    continue;
                }
                g_entries.push_back({"Part " + std::to_string(part) + " (" + PartLabel(*c, part) +
                                         " found)",
                                     [c, part] {
                                         GameDispatch("warp",
                                                      c->number + " " + std::to_string(part));
                                     }});
            }
            break;
        }
        case Page::kWarpPoints:
            g_header = "Warp points";
            for (const auto& point : WarpPoints()) {
                const Chapter* chapter = Data().ChapterOfMap(point.second);
                const std::string label = point.first;
                g_entries.push_back({label + " (" + (chapter ? chapter->name : std::string("Hub")) +
                                         ")",
                                     [label] { GameDispatch("warp", label); }});
            }
            if (g_entries.empty()) {
                g_header += "\n(none yet: !setwarp <name>)";
            }
            break;
        case Page::kTracker: {
            const Chapter* chapter = TrackedChapter();
            if (chapter == nullptr) {
                Open(Page::kTrackChapters);  // the hub: nothing to follow yet
                return;
            }
            const std::string here = CurrentMap();
            g_header = "Tracker: " + chapter->name + " [" + ChapterStatusText(*chapter) + "]\n" +
                       ItemsLine();
            if (const VehicleKey* key = Data().KeyFor(chapter->key)) {
                g_header += std::string("\n") + key->item + ": " +
                            (HeldItem(key->item) ? "held" : "not yet");
            }
            for (size_t p = 1; p <= chapter->maps.size(); ++p) {
                const int part = static_cast<int>(p);
                std::vector<const Location*> checks = PartChecks(*chapter, part);
                if (checks.empty()) {
                    continue;
                }
                g_entries.push_back({"Part " + std::to_string(part) + ": " + Count(checks) +
                                         (chapter->maps[p - 1] == here ? " (here)" : ""),
                                     [part] {
                                         g_track_part = part;
                                         Open(Page::kTrackChecks);
                                     }});
            }
            const std::vector<const Location*> weapons = WeaponChecks();
            if (!weapons.empty()) {
                g_entries.push_back({"Weapons: " + Count(weapons), [] {
                                         g_track_part = 0;
                                         Open(Page::kTrackChecks);
                                     }});
            }
            g_entries.push_back({"Track another chapter", [] { Open(Page::kTrackChapters); }});
            break;
        }
        case Page::kTrackChapters:
            g_header = "Track a chapter";
            for (const Chapter& chapter : Data().Chapters()) {
                if (State().ChapterExcluded(chapter.key)) {
                    continue;
                }
                std::vector<const Location*> checks;
                for (size_t p = 1; p <= chapter.maps.size(); ++p) {
                    for (const Location* l : PartChecks(chapter, static_cast<int>(p))) {
                        checks.push_back(l);
                    }
                }
                const Chapter* c = &chapter;
                g_entries.push_back({chapter.name + ": " + Count(checks) +
                                         (c == Data().ChapterOfMap(CurrentMap()) ? " (here)" : ""),
                                     [c] {
                                         g_tracked = c->key;
                                         Open(Page::kTracker);
                                     }});
            }
            break;
        case Page::kTrackChecks: {
            std::vector<const Location*> checks;
            const Chapter* chapter = TrackedChapter();
            if (g_track_part > 0 && chapter != nullptr) {
                checks = PartChecks(*chapter, g_track_part);
                g_header = chapter->name + ", part " + std::to_string(g_track_part);
            } else {
                checks = WeaponChecks();
                g_header = "Weapons";
            }
            g_header += ": " + Count(checks) + " found";
            // Unfound first; each picked says where it is (and traces it here).
            for (int pass = 0; pass < 2; ++pass) {
                for (const Location* location : checks) {
                    const bool done = State().checked.count(location->id) != 0;
                    if (done != (pass == 1)) {
                        continue;
                    }
                    const long id = location->id;
                    g_entries.push_back({(done ? "[done] " : "") + ShortName(location->name),
                                         [id] { Describe(id); }});
                }
            }
            if (checks.empty()) {
                g_header += "\n(nothing)";
            }
            break;
        }
        case Page::kNone:
            break;
    }
}

void Open(Page page, int first) {
    g_page = page;
    g_first = first;
    Build(page);
    Show();
}

void Back() {
    if (g_first > 0) {
        Open(g_page, (std::max)(g_first - kItemsPerPage, 0));
        return;
    }
    switch (g_page) {
        case Page::kParts:
            Open(Page::kChapters);
            break;
        case Page::kTrackChapters:
        case Page::kTrackChecks:
            if (TrackedChapter() != nullptr) {
                Open(Page::kTracker);
            } else {
                Open(Page::kMain);
            }
            break;
        case Page::kMain:
        case Page::kNone:
            Close();
            break;
        default:
            Open(Page::kMain);
            break;
    }
}

void Select(int key) {
    if (g_page == Page::kNone) {
        return;
    }
    if (key == 10 || key == 0) {
        Close();
        return;
    }
    if (key == 8) {
        Back();
        return;
    }
    if (key == 9) {
        Open(g_page, g_first + kItemsPerPage);
        return;
    }
    const int index = g_first + key - 1;
    if (key < 1 || key > kItemsPerPage || index >= static_cast<int>(g_entries.size())) {
        Show();  // a key with nothing on it: the menu stays
        return;
    }
    std::function<void()> act = g_entries[index].act;
    g_page = Page::kNone;  // the client closed it; an action may open another
    act();
}

}  // namespace

void NavPrecache() { g_beam_index = CBaseEntity::PrecacheModel(kBeamSprite); }

void NavLevelStart() {
    g_page = Page::kNone;
    g_selected = 0;
    g_tracing = false;
}

void NavFrame() {
    if (g_selected != 0) {
        const int key = g_selected;
        g_selected = 0;
        Select(key);
    }
    if (!g_tracing) {
        return;
    }
    if (State().checked.count(g_trace.id) != 0) {
        StopTrace("");  // the check going out is the answer, as in HL1
        return;
    }
    CBasePlayer* player = Player();
    if (player == nullptr || !player->IsAlive() || gpGlobals->curtime < g_next_beam) {
        return;
    }
    g_next_beam = gpGlobals->curtime + kTraceRefresh;
    DrawTrace(player);
}

bool NavSilent(const std::string& name, const std::string& rest) {
    return name == "menu" || (name == "trace" && g_tracing && Trim(rest).empty());
}

bool NavDispatch(const std::string& name, const std::string& rest) {
    if (name == "menu") {
        if (g_page != Page::kNone) {
            Close();  // the bound key toggles it
        } else {
            Open(Page::kMain);
        }
    } else if (name == "find") {
        Find(Trim(rest));
    } else if (name == "trace") {
        Trace(Trim(rest));
    } else {
        return false;
    }
    return true;
}

// `!tracker` is the console listing only; the menu opens from `!menu` alone.
// A chapter named still becomes the one the menu's tracker page follows.
void NavTracker(const std::string& filter) {
    const std::string text = Trim(filter);
    ConsoleTracker(text);
    if (const Chapter* chapter = text.empty() ? nullptr : Data().FindChapter(text)) {
        g_tracked = chapter->key;
    }
}

void NavMenuSelect(int key) { g_selected = key; }

}  // namespace ap

// The client sends this for a key pressed while the menu is open.
CON_COMMAND(menuselect, "Archipelago menu: pick an entry")
{
    if (args.ArgC() < 2) {
        return;
    }
    ap::NavMenuSelect(atoi(args.Arg(1)));
}

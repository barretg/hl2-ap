// Gameplay. See ap_game.h for what calls what; HL1's rules (decide in the
// hook, act in the frame) hold throughout.

#include "cbase.h"
#include "player.h"
#include "hl2_player.h"
#include "globalstate.h"
#include "weapon_physcannon.h"
#include "prop_combine_ball.h"
#include "basecombatweapon_shared.h"
#include "ammodef.h"
#include "filesystem.h"

#include "ap_game.h"

#include <cstdio>
#include <fstream>
#include <map>
#include <algorithm>
#include <set>
#include <string>
#include <vector>

#include "ap_bridge.h"
#include "ap_checkdata.h"
#include "ap_main.h"
#include "ap_melee.h"
#include "ap_state.h"
#include "ap_text.h"
#include "ap_nav.h"
#include "ap_traps.h"

// memdbgon must be the last include file in a .cpp file!!!
#include "tier0/memdbgon.h"

// player.cpp: set while `impulse 101` hands out every weapon.
extern int gEvilImpulse101;

namespace ap {
namespace {

// Item names the dll acts on by name. tests/test_game_names.py checks each
// is an item in campaign.json, so a rename cannot silently ungate one.
const char* const kSuitItem = "HEV Suit";
const char* const kFlashlightItem = "Flashlight";
const char* const kAuxPowerItem = "Progressive Aux Power";
const int kAuxPowerStages = 4;
const char* const kAirboatGunItem = "Airboat Gun";
const char* const kBuggyGunItem = "Buggy Gun";
const char* const kGravityGunItem = "Progressive Gravity Gun";
const char* const kPhyscannon = "weapon_physcannon";

// Vehicle classes by the script checkdata names a key with.
struct VehicleClass {
    const char* script;
    const char* classname;
};
const VehicleClass kVehicleClasses[] = {
    {"scripts/vehicles/airboat.txt", "prop_vehicle_airboat"},
    {"scripts/vehicles/jeep_test.txt", "prop_vehicle_jeep"},
};

// --- per-map state ---------------------------------------------------------

// Checks this map has found that the client has not been told about yet:
// held until the run authorises this map (see `Authorised`).
std::set<long> g_owed;
// Checks already sent from this map: a pickup that keeps firing until the
// server confirms it must not resend (or re-announce) every frame.
std::set<long> g_sent;
// Whether this map has been judged against the snapshot yet.
bool g_judged = false;
// A player_weaponstrip fired here: the loadout stops granting until the
// next map, or it would hand back what the level just took.
bool g_stripped = false;
// When the warp save for this map is due, or < 0.
double g_save_due = -1.0;
bool g_upgrade_sent = false;
// Consumable weapons granted on this map: a thrown-away last grenade must not
// come back every second.
std::set<std::string> g_granted_here;
bool g_goal_sent = false;
// The hub's start was checked for the player being inside geometry.
bool g_unstuck = false;
// Refusal notices, by what was refused, so one held trigger is one line.
std::map<std::string, double> g_last_notice;
const double kNoticeRepeatSeconds = 10.0;
// "Found:" repeats until the server confirms the check.
const double kFoundRepeatSeconds = 5.0;

// --- across maps -----------------------------------------------------------

// The slot last seen, for noticing a different one connecting.
std::string g_last_slot;
// Item names held at the last snapshot, for "Received" notices.
std::set<std::string> g_last_items;
// Why the hub was loaded, shown once it is up: said on the map being left,
// it is gone before the screen draws.
std::string g_hub_reason;
std::map<std::string, int> g_last_counts;
bool g_have_items = false;
bool g_version_warned = false;
// Our own grants pass the gate.
bool g_granting = false;
// DeathLink: deaths forgiven since the last one sent, and a window after an
// incoming DeathLink in which a death is ours to ignore.
int g_forgiven = 0;
double g_immune_until = 0.0;
double g_last_death = -100.0;
const double kDeathLinkImmunitySeconds = 2.0;
const double kRevertDebounceSeconds = 15.0;
const long kDeathLinkFreshSeconds = 10;

bool Debounced(const std::string& key, double window = kNoticeRepeatSeconds) {
    const double now = Now();
    auto it = g_last_notice.find(key);
    if (it != g_last_notice.end() && now - it->second < window) {
        return false;
    }
    g_last_notice[key] = now;
    return true;
}

std::string ItemOf(const std::string& classname) {
    return Data().GateOf(classname);
}

bool Holds(const std::string& item) {
    if (!Gating()) {
        return true;
    }
    return State().Count(item) >= 1;
}

bool ClassnameHeld(const std::string& classname) {
    const std::string item = ItemOf(classname);
    if (item.empty() || State().Ungated(classname)) {
        return true;
    }
    for (const std::string& start : State().starting_weapons) {
        if (start == classname) {
            return true;
        }
    }
    return Holds(item);
}

std::string LocationName(long id) {
    const Location* location = Data().LocationById(id);
    return location ? location->name : std::to_string(id);
}

const Chapter* CurrentChapter() { return Data().ChapterOfMap(CurrentMap()); }

bool IsHub() { return !Data().Hub().empty() && CurrentMap() == Data().Hub(); }

bool ChapterAvailable(const Chapter& chapter) {
    return State().ChapterOpen(chapter.key) && !State().ChapterExcluded(chapter.key);
}

bool ChapterDone(const Chapter& chapter) {
    const long id = Data().ChapterComplete(chapter.key);
    return id != 0 && State().checked.count(id) != 0;
}

// May this map's checks reach the client? Only once a snapshot says the run
// may be here: the engine restores the last save on death, and that save can
// be from another seed. Unconnected is "wait", never "no".
bool Authorised() {
    const Snapshot& state = State();
    if (state.session.empty() || !state.connected || !g_judged) {
        return false;
    }
    return state.data_version == Data().DataVersion();
}

void Flush() {
    if (!Authorised()) {
        return;
    }
    for (long id : g_owed) {
        if (State().checked.count(id) == 0 && State().InSeed(id)) {
            Wire().Send("CHECK", std::to_string(id));
            g_sent.insert(id);
        }
    }
    g_owed.clear();
}

// A location was found. Sent now if this map is authorised, else held.
void Found(long id) {
    // Only a chapter's maps hold locations: the hub's touches never count.
    if (id == 0 || !Data().Loaded() || CurrentChapter() == nullptr) {
        return;
    }
    if (State().checked.count(id) != 0 || g_owed.count(id) != 0 || g_sent.count(id) != 0 ||
        !State().InSeed(id)) {
        return;
    }
    // Held even before any client has named a slot: it is sent once one does
    // and authorises this map.
    g_owed.insert(id);
    if (Gating() && Debounced("found:" + std::to_string(id), kFoundRepeatSeconds)) {
        Notify("Found: " + LocationName(id));
    }
    Flush();
}

void GoHub(const std::string& why) {
    if (Data().Hub().empty()) {
        return;
    }
    g_hub_reason = why;
    RequestMap(Data().Hub());
}

// --- warp saves --------------------------------------------------------------

// FNV-1a of the slot: saves of different runs never collide, and a run's
// can be swept by prefix.
std::string SlotKey() {
    const std::string& slot = State().slot;
    if (slot.empty()) {
        return "";
    }
    unsigned int hash = 2166136261u;
    for (unsigned char c : slot) {
        hash ^= c;
        hash *= 16777619u;
    }
    char text[16];
    Q_snprintf(text, sizeof(text), "%08x", hash);
    return text;
}

std::string WarpSaveName(const std::string& map) {
    const std::string key = SlotKey();
    return key.empty() ? std::string() : "apw_" + key + "_" + map;
}

bool SaveExists(const std::string& name) {
    char dir[MAX_PATH] = {0};
    engine->GetGameDir(dir, sizeof(dir));
    std::ifstream file((std::string(dir) + "/save/" + name + ".sav").c_str());
    return static_cast<bool>(file);
}

// The player's own warp points, `!setwarp <name>`: `apw_<key>_u<label>_<map>`.
// The label is letters and digits only, so the last underscore splits it from
// the map. The directory is the record; nothing about them is kept in memory.
struct NamedWarp {
    std::string save;
    std::string label;
    std::string map;
};

std::string SaveDir() {
    char dir[MAX_PATH] = {0};
    engine->GetGameDir(dir, sizeof(dir));
    return std::string(dir) + "/save/";
}

std::string WarpLabel(const std::string& text) {
    std::string out;
    for (char c : Lower(text)) {
        if (((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9')) && out.size() < 12) {
            out.push_back(c);
        }
    }
    return out;
}

std::vector<NamedWarp> NamedWarps() {
    std::vector<NamedWarp> found;
    const std::string key = SlotKey();
    if (key.empty()) {
        return found;
    }
    const std::string prefix = "apw_" + key + "_u";
    FileFindHandle_t handle;
    for (const char* file = filesystem->FindFirstEx(("save/" + prefix + "*.sav").c_str(), "MOD",
                                                    &handle);
         file != nullptr; file = filesystem->FindNext(handle)) {
        std::string name = file;
        if (name.size() <= prefix.size() + 4) {
            continue;
        }
        name = name.substr(0, name.size() - 4);
        const std::string tail = name.substr(prefix.size());
        const size_t split = tail.find('_');
        if (split == std::string::npos || split == 0 || split + 1 >= tail.size()) {
            continue;
        }
        found.push_back({name, tail.substr(0, split), tail.substr(split + 1)});
    }
    filesystem->FindClose(handle);
    std::sort(found.begin(), found.end(),
              [](const NamedWarp& a, const NamedWarp& b) { return a.label < b.label; });
    return found;
}

const NamedWarp* FindNamedWarp(const std::vector<NamedWarp>& warps, const std::string& text) {
    const std::string label = WarpLabel(text);
    for (const NamedWarp& warp : warps) {
        if (!label.empty() && warp.label == label) {
            return &warp;
        }
    }
    return nullptr;
}

// --- loadout -------------------------------------------------------------------

bool Confiscated() {
    // From the Citadel's field on, only the gravity gun is carried.
    return GlobalEntity_GetState("super_phys_gun") == GLOBAL_ON;
}

// Weapons that leave the inventory when used up.
bool IsConsumable(const std::string& classname) { return classname == "weapon_frag"; }

CBaseCombatWeapon* Owned(CBasePlayer* player, const std::string& classname) {
    return player->Weapon_OwnsThisType(classname.c_str());
}

bool InSolid(CBasePlayer* player, const Vector& at) {
    trace_t tr;
    UTIL_TraceHull(at, at, player->GetPlayerMins(), player->GetPlayerMaxs(), MASK_PLAYERSOLID,
                   player, COLLISION_GROUP_PLAYER_MOVEMENT, &tr);
    return tr.startsolid;
}

// Moves a player spawned inside geometry to the nearest open spot, searched
// in rings outward and upward. The stand-in hub's start sits in a wall. At
// most a few hundred hull traces, once per map.
void Unstick(CBasePlayer* player) {
    const Vector origin = player->GetAbsOrigin();
    if (player->GetMoveType() == MOVETYPE_NOCLIP || !InSolid(player, origin)) {
        return;
    }
    for (int ring = 1; ring <= 8; ++ring) {
        const float reach = 24.0f * ring;
        for (float up : {0.0f, 32.0f, 72.0f}) {
            for (int step = 0; step < 16; ++step) {
                const float angle = 2.0f * M_PI_F * step / 16;
                const Vector at = origin + Vector(reach * cosf(angle), reach * sinf(angle), up);
                if (!InSolid(player, at)) {
                    player->Teleport(&at, nullptr, &vec3_origin);
                    return;
                }
            }
        }
    }
}

// As in the first game, a weapon handed over comes with half the ammo its
// type can be carried at (rounded up), magazine first, not the default load a
// pickup carries; what the player already had of that type stays if it is
// more. Alt-fire ammo (SMG grenades, energy balls) starts at 2. `reserve`
// holds the counts from before the grant.
void KitAmmo(CBasePlayer* player, CBaseCombatWeapon* weapon, const int* reserve) {
    for (int i = 0; i < MAX_AMMO_SLOTS; ++i) {
        player->SetAmmoCount(reserve[i], i);
    }
    const int secondary = weapon->GetSecondaryAmmoType();
    if (secondary >= 0 && player->GetAmmoCount(secondary) < 2) {
        player->SetAmmoCount(2, secondary);
    }
    const int primary = weapon->GetPrimaryAmmoType();
    if (primary < 0) {
        return;
    }
    int load = (GetAmmoDef()->MaxCarry(primary) + 1) / 2;
    if (weapon->UsesClipsForAmmo1()) {
        weapon->m_iClip1 = Min(load, weapon->GetMaxClip1());
        load -= weapon->m_iClip1;
    }
    if (player->GetAmmoCount(primary) < load) {
        player->SetAmmoCount(load, primary);
    }
}

// Exactly idempotent: runs on every spawn and every snapshot change.
void ApplyLoadout() {
    CBasePlayer* player = Player();
    if (player == nullptr || !player->IsAlive() || !ClientReady() || !Gating() ||
        !Data().Loaded()) {
        return;
    }
    if (!player->IsSuitEquipped()) {
        player->EquipSuit(false);
    }
    if (!Holds(kSuitItem) && player->ArmorValue() > 0) {
        player->SetArmorValue(0);
    }
    for (const auto& gate : Data().Gates()) {
        const std::string& classname = gate.first;
        if (!StartsWith(classname, "weapon_")) {
            continue;
        }
        const bool held = ClassnameHeld(classname);
        CBaseCombatWeapon* owned = Owned(player, classname);
        if (held && owned == nullptr) {
            if (g_stripped || (Confiscated() && classname != kPhyscannon)) {
                continue;
            }
            if (classname == "weapon_crowbar" && CrowbarThrown()) {
                continue;  // it comes back by itself
            }
            if (Withheld(classname)) {
                continue;  // Butterfingers: on the floor until picked up or reissued
            }
            if (IsConsumable(classname) && g_granted_here.count(classname) != 0) {
                continue;  // once per map; used up is used up
            }
            if (InSolid(player, player->GetAbsOrigin())) {
                continue;  // it could not be picked up; waits for open ground
            }
            int reserve[MAX_AMMO_SLOTS];
            for (int i = 0; i < MAX_AMMO_SLOTS; ++i) {
                reserve[i] = player->GetAmmoCount(i);
            }
            CBaseEntity* given = GrantWeapon(player, classname.c_str());
            CBaseCombatWeapon* granted = Owned(player, classname);
            if (granted == nullptr) {
                // Never left lying about, where a later touch would count.
                if (given != nullptr) {
                    UTIL_Remove(given);
                }
                continue;
            }
            KitAmmo(player, granted, reserve);
            g_granted_here.insert(classname);
        } else if (!held && owned != nullptr) {
            if (player->GetActiveWeapon() == owned) {
                player->ClearActiveWeapon();
            }
            player->RemovePlayerItem(owned);
            UTIL_Remove(owned);
        }
    }
    if (player->GetActiveWeapon() == nullptr) {
        player->SwitchToNextBestWeapon(nullptr);
    }
}

// --- hub -----------------------------------------------------------------------

// The stand-in hub is a menu background: its camera, zoom and scripted
// relays would hold the player's view, so they go before they can fire.
void TidyHub() {
    static const char* const kHubStrip[] = {
        "logic_auto", "point_viewcontrol", "env_zoom", "trigger_multiple",
        "logic_autosave", "func_monitor",
    };
    for (const char* classname : kHubStrip) {
        CBaseEntity* entity = nullptr;
        while ((entity = gEntList.FindEntityByClassname(entity, classname)) != nullptr) {
            UTIL_Remove(entity);
        }
    }
}

// --- judging the map -------------------------------------------------------------

// Once per map, when a snapshot is in: may the run be here at all?
void Judge() {
    if (g_judged || !Gating() || !State().connected || !Data().Loaded()) {
        return;
    }
    if (State().data_version != Data().DataVersion()) {
        if (!g_version_warned) {
            g_version_warned = true;
            Notify("This mod's checkdata.txt does not match the client's apworld "
                   "(data version " + Data().DataVersion() + " vs " + State().data_version +
                   "). Checks are paused; reinstall the mod from the client with /install.");
        }
        return;
    }
    g_judged = true;
    const Chapter* chapter = CurrentChapter();
    if (chapter != nullptr && !ChapterAvailable(*chapter)) {
        g_owed.clear();
        GoHub(chapter->name + (State().ChapterExcluded(chapter->key)
                                   ? " is not in this seed. Back to the hub."
                                   : " is locked. Back to the hub."));
        return;
    }
    if (chapter != nullptr) {
        const long reached = Data().MapReached(CurrentMap());
        Found(reached);
        if (Data().ChapterOfMap(CurrentMap()) && SaveExists(WarpSaveName(CurrentMap())) == false) {
            g_save_due = Now() + 3.0;
        }
    }
    if (IsHub()) {
        if (!g_hub_reason.empty()) {
            Notify(g_hub_reason);
            g_hub_reason.clear();
        }
        Notify("Hub. !ap lists chapters; !warp <number or name> starts one.");
    }
    Flush();
}

// --- items -------------------------------------------------------------------------

void ApplyFiller(const std::string& name) {
    CBasePlayer* player = Player();
    if (player == nullptr || !player->IsAlive()) {
        return;
    }
    if (name == "Ammo Cache") {
        for (int i = 0; i < player->WeaponCount(); ++i) {
            CBaseCombatWeapon* weapon = player->GetWeapon(i);
            if (weapon == nullptr) {
                continue;
            }
            if (weapon->GetPrimaryAmmoType() >= 0) {
                player->GiveAmmo(Max(weapon->GetDefaultClip1(), 1) * 2,
                                 weapon->GetPrimaryAmmoType(), true);
            }
            if (weapon->GetSecondaryAmmoType() >= 0) {
                player->GiveAmmo(1, weapon->GetSecondaryAmmoType(), true);
            }
        }
        Notify("Ammo Cache: every weapon you hold topped up.");
    } else if (name == "Medkit") {
        player->TakeHealth(25, DMG_GENERIC);
        Notify("Medkit: +25 health.");
    } else if (name == "Battery") {
        if (Holds(kSuitItem)) {
            player->IncrementArmorValue(15, 100);
            Notify("Battery: +15 armour.");
        } else {
            Notify("Battery: no HEV Suit yet, so no armour.");
        }
    } else {
        Notify("Received " + name + " (no effect in this build).");
    }
}

void DeathLinkArrived(const PendingEvent& event) {
    if (!State().OptionBool("death_link", false)) {
        return;
    }
    if (event.stamp > 0 && Wire().Now() - event.stamp > kDeathLinkFreshSeconds) {
        return;  // stale: the player was not here for it
    }
    CBasePlayer* player = Player();
    if (player == nullptr || !player->IsAlive()) {
        return;
    }
    const size_t tilde = event.payload.find('~');
    const std::string source = event.payload.substr(0, tilde);
    const std::string cause = tilde == std::string::npos ? "" : event.payload.substr(tilde + 1);
    Notify("DeathLink from " + source + (cause.empty() ? "" : " (" + cause + ")") + ".");
    g_immune_until = Now() + kDeathLinkImmunitySeconds;
    player->CommitSuicide(false, true);
}

void ReportDeath(const std::string& cause) {
    if (!Gating() || Now() < g_immune_until) {
        return;
    }
    g_last_death = Now();
    const bool link = State().OptionBool("death_link", false);
    const long allowance = State().OptionLong("death_link_amnesty", 0);
    bool forgiven = false;
    if (link && g_forgiven < allowance) {
        ++g_forgiven;
        forgiven = true;
        const long left = allowance - g_forgiven;
        Notify(left > 0 ? "Death forgiven; " + std::to_string(left) +
                              " more before one is sent."
                        : std::string("Death forgiven; the next "
                                      "one will be sent."));
    } else {
        g_forgiven = 0;
        if (link && allowance > 0) {
            Notify("DeathLink sent. Amnesty is back to " + std::to_string(allowance) + ".");
        }
    }
    Wire().Send("DEATH", std::vector<std::string>{"Freeman", Sanitise(cause),
                                                  forgiven ? "1" : "0"});
}

// --- commands ----------------------------------------------------------------------

std::string ChapterStatus(const Chapter& chapter) {
    if (State().ChapterExcluded(chapter.key)) {
        return "not in this seed";
    }
    if (ChapterDone(chapter)) {
        return "complete";
    }
    if (State().ChapterOpen(chapter.key)) {
        return chapter.is_goal ? "OPEN" : "unlocked";
    }
    return chapter.is_goal ? "sealed" : "locked";
}

void ListChapters() {
    BeginReply("!ap");
    for (const Chapter& chapter : Data().Chapters()) {
        Say(chapter.number + ". " + chapter.name + " [" + ChapterStatus(chapter) + "]");
    }
    EndReply();
}

// A named warp point. The save says where; the seed still says whether.
void WarpToNamed(const NamedWarp& warp) {
    const Chapter* chapter = Data().ChapterOfMap(warp.map);
    if (chapter == nullptr) {
        // The hub is always open; anywhere else outside a chapter never is.
        if (warp.map != Data().Hub()) {
            Notify("Warp point " + warp.label + " is outside any chapter.");
            return;
        }
    } else if (Gating() && !ChapterAvailable(*chapter)) {
        Notify(chapter->name + " is " + ChapterStatus(*chapter) + ".");
        return;
    }
    if (chapter != nullptr && Gating() && warp.map != chapter->maps.front() &&
        State().checked.count(Data().MapReached(warp.map)) == 0) {
        Notify("Warp point " + warp.label + " is in a part this run has not reached.");
        return;
    }
    Notify("Warping to " + warp.label + ".");
    engine->ServerCommand(("load " + warp.save + "\n").c_str());
}

void SetWarp(const std::string& rest) {
    const std::string key = SlotKey();
    if (key.empty()) {
        Notify("No slot is connected, so there is nothing to key a warp point to.");
        return;
    }
    const std::string map = CurrentMap();
    const Chapter* chapter = Data().ChapterOfMap(map);
    if (chapter == nullptr && !IsHub()) {
        Notify("Warp points can only be set inside a chapter or the hub.");
        return;
    }
    CBasePlayer* player = UTIL_GetLocalPlayer();
    if (player == nullptr || !player->IsAlive()) {
        Notify("Not while dead.");
        return;
    }
    if (Trim(rest).empty()) {
        if (chapter == nullptr) {
            Notify("The hub has no part warp point; !setwarp <name> makes one here.");
            return;
        }
        engine->ServerCommand(("save " + WarpSaveName(map) + "\n").c_str());
        const auto at = std::find(chapter->maps.begin(), chapter->maps.end(), map);
        const int part = static_cast<int>(at - chapter->maps.begin()) + 1;
        Notify("Warp point for " + chapter->name + " part " + std::to_string(part) +
               " set to where you stand.");
        return;
    }
    const std::string label = WarpLabel(rest);
    if (label.empty()) {
        Notify("A warp point name needs letters or numbers: !setwarp lab");
        return;
    }
    // The same name elsewhere is that warp point moved: one name, one save.
    const std::vector<NamedWarp> warps = NamedWarps();
    const NamedWarp* existing = FindNamedWarp(warps, label);
    if (existing != nullptr && existing->map != map) {
        std::remove((SaveDir() + existing->save + ".sav").c_str());
    }
    engine->ServerCommand(("save apw_" + key + "_u" + label + "_" + map + "\n").c_str());
    Notify("Warp point " + label + " set. Come back with !warp " + label + ".");
}

void ListWarps() {
    BeginReply("!warps");
    const std::vector<NamedWarp> warps = NamedWarps();
    if (warps.empty()) {
        Say("No warp points of your own. !setwarp <name> makes one where you stand.");
    }
    for (const NamedWarp& warp : warps) {
        const Chapter* chapter = Data().ChapterOfMap(warp.map);
        Say("!warp " + warp.label + "    " + (chapter ? chapter->name : std::string("Hub")) +
            " (" + warp.map + ")");
    }
    Say("Parts you have reached: !warp <chapter> <part>.");
    EndReply();
}

void Warp(const std::string& rest) {
    const std::vector<std::string> words = Split(Trim(rest), ' ');
    if (Trim(rest).empty()) {
        Notify("Usage: !warp <chapter number or name> [part]");
        return;
    }
    // A trailing number is a part when the rest names a chapter.
    std::string name = Trim(rest);
    int part = 0;
    if (words.size() >= 2) {
        std::string last = Lower(words.back());
        if (StartsWith(last, "p")) {
            last = last.substr(1);
        }
        std::string head;
        for (size_t i = 0; i + 1 < words.size(); ++i) {
            head += (head.empty() ? "" : " ") + words[i];
        }
        if (ParseLong(last, -1) > 0 && Data().FindChapter(head) != nullptr) {
            part = static_cast<int>(ParseLong(last));
            name = head;
        }
    }
    const Chapter* chapter = Data().FindChapter(name);
    if (chapter == nullptr) {
        const std::vector<NamedWarp> warps = NamedWarps();
        if (const NamedWarp* warp = FindNamedWarp(warps, Trim(rest))) {
            WarpToNamed(*warp);
            return;
        }
        Notify("No chapter or warp point called " + name + ". !ap and !warps list them.");
        return;
    }
    if (Gating() && !ChapterAvailable(*chapter)) {
        Notify(chapter->name + " is " + ChapterStatus(*chapter) + ".");
        return;
    }
    // No part starts the chapter fresh; part 1 named is its warp point, which
    // `!setwarp` may have moved.
    if (part == 0) {
        RequestMap(chapter->maps.front());
        return;
    }
    if (part > static_cast<int>(chapter->maps.size())) {
        Notify(chapter->name + " has " + std::to_string(chapter->maps.size()) + " parts.");
        return;
    }
    const std::string& map = chapter->maps[part - 1];
    if (part > 1 && Gating() && State().checked.count(Data().MapReached(map)) == 0) {
        Notify("You have not reached part " + std::to_string(part) + " of " + chapter->name +
               " yet.");
        return;
    }
    const std::string save = WarpSaveName(map);
    if (!save.empty() && SaveExists(save)) {
        engine->ServerCommand(("load " + save + "\n").c_str());
    } else {
        RequestMap(map);
    }
}

void Tracker() {
    BeginReply("!tracker");
    const std::string map = CurrentMap();
    int found = 0;
    int missing = 0;
    for (const Location& location : Data().Locations()) {
        if (location.map != map || !State().InSeed(location.id)) {
            continue;
        }
        if (State().checked.count(location.id) != 0) {
            ++found;
        } else {
            ++missing;
            Say("  missing: " + location.name);
        }
    }
    Say(map + ": " + std::to_string(found) + " found, " + std::to_string(missing) + " missing.");
    EndReply();
}

// The kit a map spawns at the player when loaded directly rather than through
// a level change (`logic_auto` OnNewGame templates): not a pickup.
bool NewGameKit(CBaseEntity* entity) {
    return Data().IsKit(CurrentMap(), STRING(entity->GetEntityName()));
}

// Received items replace the kit in a run, so it never stays spawned: left in,
// it piles up beside the grants at the player's feet.
class KitRemover : public IEntityListener {
public:
    void OnEntitySpawned(CBaseEntity* entity) override {
        if (entity != nullptr && Gating() && NewGameKit(entity)) {
            UTIL_Remove(entity);
        }
    }
};
KitRemover g_kit_remover;
bool g_kit_listening = false;

}  // namespace

// --- public ------------------------------------------------------------------------

bool Gating() { return !State().slot.empty() && Data().Loaded(); }

std::string ChapterStatusText(const Chapter& chapter) { return ChapterStatus(chapter); }

bool WarpOpen(const Chapter& chapter) { return !Gating() || ChapterAvailable(chapter); }

bool PartOpen(const Chapter& chapter, int part) {
    if (part < 1 || part > static_cast<int>(chapter.maps.size())) {
        return false;
    }
    return part == 1 || !Gating() ||
           State().checked.count(Data().MapReached(chapter.maps[part - 1])) != 0;
}

std::vector<std::pair<std::string, std::string>> WarpPoints() {
    std::vector<std::pair<std::string, std::string>> points;
    for (const NamedWarp& warp : NamedWarps()) {
        points.emplace_back(warp.label, warp.map);
    }
    return points;
}

bool HeldItem(const std::string& item) { return Holds(item); }

void GameLevelStart() {
    Data().Load(StoreDir() + "/checkdata.txt");
    g_owed.clear();
    g_sent.clear();
    g_judged = false;
    g_stripped = false;
    g_save_due = -1.0;
    g_upgrade_sent = false;
    g_goal_sent = false;
    g_unstuck = false;
    g_last_notice.clear();
    g_granted_here.clear();
    TrapsLevelStart();
    NavLevelStart();
    if (!g_kit_listening) {
        gEntList.AddListenerEntity(&g_kit_remover);
        g_kit_listening = true;
    }
    if (Gating()) {
        for (CBaseEntity* e = gEntList.FirstEnt(); e != nullptr; e = gEntList.NextEnt(e)) {
            if (NewGameKit(e)) {
                UTIL_Remove(e);
            }
        }
    }
    if (IsHub()) {
        TidyHub();
    }
}

void GameSnapshotChanged() {
    const Snapshot& state = State();
    if (!state.slot.empty() && !g_last_slot.empty() && state.slot != g_last_slot) {
        g_have_items = false;
        g_forgiven = 0;
        if (!IsHub()) {
            GoHub("A different slot connected. Back to the hub.");
        }
    }
    if (!state.slot.empty()) {
        g_last_slot = state.slot;
    }
    if (g_have_items) {
        for (const std::string& item : state.held_items) {
            const auto count = state.counts.find(item);
            const auto before = g_last_counts.find(item);
            if (count != state.counts.end()) {
                const int had = before == g_last_counts.end() ? 0 : before->second;
                if (count->second > had) {
                    Notify("Received: " + item + " (" + std::to_string(count->second) + ")");
                }
            } else if (g_last_items.count(item) == 0) {
                Notify("Received: " + item);
            }
        }
    }
    if (!state.session.empty()) {
        g_last_items = state.held_items;
        g_last_counts = state.counts;
        g_have_items = true;
    }
    Judge();
    Flush();
    ApplyLoadout();
}

void GameEvent(const PendingEvent& event) {
    if (event.kind == "ITEM") {
        ApplyFiller(event.payload);
    } else if (event.kind == "DEATHLINK") {
        DeathLinkArrived(event);
    } else if (event.kind == "TRAP") {
        QueueTrap(event.payload);
    }
}

void GameFrame() {
    Judge();
    CBasePlayer* player = Player();
    if (player == nullptr || !ClientReady()) {
        return;
    }
    if (IsHub() && !g_unstuck && player->IsAlive()) {
        g_unstuck = true;
        Unstick(player);
    }
    TrapsFrame();
    NavFrame();
    static int frame = 0;
    if (++frame % 30 == 0) {
        ApplyLoadout();  // catches spawns and quickloads without a hook
    }
    if (Gating() && !Holds(kSuitItem) && player->ArmorValue() > 0) {
        player->SetArmorValue(0);
    }
    if (!g_upgrade_sent && Gating() && PlayerHasMegaPhysCannon() &&
        Owned(player, kPhyscannon) != nullptr) {
        g_upgrade_sent = true;
        Found(Data().Pickup("weapon_upgrade", kPhyscannon));
    }
    if (g_save_due > 0 && Now() >= g_save_due && player->IsAlive() && Authorised()) {
        g_save_due = -1.0;
        const std::string save = WarpSaveName(CurrentMap());
        if (!save.empty() && !SaveExists(save)) {
            engine->ServerCommand(("save " + save + "\n").c_str());
        }
    }
}

bool GameDispatch(const std::string& name, const std::string& rest) {
    if (name == "ap" || name == "chapters" || name == "missions") {
        ListChapters();
    } else if (name == "warp") {
        Warp(rest);
    } else if (name == "hub") {
        GoHub("");
    } else if (name == "setwarp") {
        SetWarp(rest);
    } else if (name == "warps") {
        ListWarps();
    } else if (name == "tracker") {
        Tracker();
        NavTracker(rest);
    } else {
        return NavDispatch(name, rest);
    }
    return true;
}

void GameHelp() {
    Say("!ap          every chapter and its status");
    Say("!warp <n>    start a chapter (number or name); !warp <n> <part> a part reached");
    Say("!setwarp     move this part's warp point to where you stand");
    Say("!setwarp <name>  make a warp point here; !warp <name> returns");
    Say("!warps       your warp points");
    Say("!hub         back to the hub");
    Say("!tracker [text]  checks found and missing on this map, as a menu too");
    Say("!menu        the navigation menu (bound to the - key)");
    Say("!find [text] the nearest unfound check, and which way it is");
    Say("!trace [text]  draws the way to it; again to stop");
}

void GameStatus() {
    const Chapter* chapter = CurrentChapter();
    Say(chapter ? "Chapter " + chapter->name + " [" + ChapterStatus(*chapter) + "]"
                : std::string(IsHub() ? "In the hub" : "Not in a chapter"));
    if (Gating()) {
        Say("Aux power cap " + std::to_string(static_cast<int>(AuxPowerCap())) + "%");
        Say("Gravity gun stage " + std::to_string(GravityGunStage()) + ", suit " +
            (Holds(kSuitItem) ? "on" : "off") + ", flashlight " +
            (Holds(kFlashlightItem) ? "on" : "off"));
    }
}

Touch WeaponTouch(CBasePlayer* player, CBaseCombatWeapon* weapon) {
    // The weapon Butterfingers threw is the player's own: never a check.
    switch (TrapDropTouched(weapon)) {
        case TrapDrop::kTooSoon:
            return Touch::kRefuse;
        case TrapDrop::kTaken:
            return Touch::kAllow;
        case TrapDrop::kNotTrap:
            break;
    }
    if (player == nullptr || weapon == nullptr || !Gating() || g_granting) {
        return Touch::kAllow;
    }
    const std::string classname = weapon->GetClassname();
    if (ItemOf(classname).empty() || !StartsWith(classname, "weapon_")) {
        return Touch::kAllow;
    }
    if (gEvilImpulse101) {
        return Touch::kAllow;  // a cheat give RefuseGive let through: no check
    }
    if (!NewGameKit(weapon)) {
        Found(Data().Pickup("weapon_pickup", classname));
    }
    if (ClassnameHeld(classname)) {
        return Touch::kAllow;
    }
    if (Debounced("refuse:" + classname)) {
        Notify(ItemOf(classname) + " not received yet; left where it is.");
    }
    return Touch::kRefuse;
}

// A fresh, unscripted copy of a refused weapon on the floor in front of the
// player, to be picked up once its item arrives. A fresh copy, free of the
// level's template and outputs.
void DropForLater(CBasePlayer* player, const char* classname) {
    Vector forward;
    AngleVectors(QAngle(0, player->EyeAngles().y, 0), &forward);
    // Chest high and clear of the player's box, backed off toward them if a
    // wall is closer, then down to the floor.
    const Vector from = player->WorldSpaceCenter();
    trace_t tr;
    UTIL_TraceLine(from, from + forward * 48.0f, MASK_SOLID, player, COLLISION_GROUP_NONE, &tr);
    const Vector ahead = from + forward * MAX(48.0f * tr.fraction - 8.0f, 0.0f);
    UTIL_TraceLine(ahead, ahead - Vector(0, 0, 256.0f), MASK_SOLID, player, COLLISION_GROUP_NONE,
                   &tr);
    CBaseEntity* weapon = CreateEntityByName(classname);
    if (weapon == nullptr) {
        return;
    }
    weapon->SetAbsOrigin(tr.endpos + Vector(0, 0, 8.0f));
    weapon->SetAbsAngles(QAngle(0, player->EyeAngles().y + 90.0f, 0));
    DispatchSpawn(weapon);
    // Kept for the player: Odessa, a citizen who picks up weapons, otherwise
    // takes his RPG straight back (it looked as if it vanished).
    if (CBaseCombatWeapon* gun = dynamic_cast<CBaseCombatWeapon*>(weapon)) {
        gun->Lock(1.0e6f, player);
    }
}

void ScriptedWeaponRefused(CBasePlayer* player, CBaseCombatWeapon* weapon) {
    if (player == nullptr || weapon == nullptr) {
        return;
    }
    DropForLater(player, weapon->GetClassname());
    UTIL_Remove(weapon);
}

bool RefuseGive(CBasePlayer* player, const char* classname) {
    if (player == nullptr || classname == nullptr || !Gating() || g_granting) {
        return false;
    }
    // Weapons only: the suit (`give item_suit` in Dark Energy) is ours to
    // equip, gated by armour rather than by the give.
    if (ItemOf(classname).empty() || !StartsWith(classname, "weapon_")) {
        return false;
    }
    // `impulse 101` is a cheat, not a pickup: no checks, and what is not
    // received yet is simply not given rather than dropped for later.
    if (gEvilImpulse101) {
        return !ClassnameHeld(classname);
    }
    Found(Data().Pickup("weapon_pickup", classname));
    if (ClassnameHeld(classname)) {
        return false;
    }
    if (Debounced(std::string("refuse:") + classname)) {
        Notify(ItemOf(classname) + " not received yet; left on the floor for when it does.");
    }
    DropForLater(player, classname);
    return true;
}

void SuitTouched(CBasePlayer* player, CBaseEntity* suit) {
    if (player != nullptr && suit != nullptr && !NewGameKit(suit)) {
        Found(Data().Pickup("item_pickup", "item_suit"));
    }
}

void ChargerUsed(CBaseEntity* charger, CBaseEntity* user) {
    if (charger == nullptr || user == nullptr || !user->IsPlayer()) {
        return;
    }
    // The nearest charger check of this class on this map, within reach of
    // the unit's origin: positions are rounded in the data, never compared
    // exactly.
    const Vector at = charger->GetAbsOrigin();
    const std::string classname = charger->GetClassname();
    long best = 0;
    float best_distance = 64.0f * 64.0f;
    for (const Location* location : Data().Chargers(CurrentMap())) {
        if (!StartsWith(location->arg, classname + "@")) {
            continue;
        }
        const Vector there(location->position[0], location->position[1], location->position[2]);
        const float distance = (there - at).LengthSqr();
        if (distance < best_distance) {
            best_distance = distance;
            best = location->id;
        }
    }
    Found(best);
}

bool BlockChangeLevel(const char* next_map) {
    if (next_map == nullptr || !Gating() || !Data().Loaded()) {
        return false;
    }
    const std::string from = CurrentMap();
    const std::string to = Lower(next_map);
    const Chapter* here = Data().ChapterOfMap(from);
    const Chapter* there = Data().ChapterOfMap(to);
    if (here != nullptr) {
        for (const auto& exit : here->exits) {
            if (exit.first == from && exit.second == to) {
                Found(Data().ChapterComplete(here->key));
                Wire().Send("COMPLETE", here->key);
                GoHub(here->name + " complete! Back to the hub.");
                return true;
            }
        }
    }
    if (there != nullptr && there != here && !ChapterAvailable(*there)) {
        if (Debounced("changelevel:" + to)) {
            Notify(there->name + " is " + ChapterStatus(*there) + "; that way is closed.");
        }
        return true;
    }
    return false;
}

void PlayerKilled() { ReportDeath("death"); }

void ReloadFired() {
    CBasePlayer* player = Player();
    if (player != nullptr && !player->IsAlive()) {
        return;  // already counted as a death
    }
    if (Now() - g_last_death < kRevertDebounceSeconds) {
        return;
    }
    ReportDeath("a failed objective");
}

void OutroCredits() {
    const Chapter* chapter = CurrentChapter();
    if (chapter == nullptr || !chapter->is_goal || g_goal_sent || !Gating()) {
        return;
    }
    g_goal_sent = true;
    Found(Data().ChapterComplete(chapter->key));
    Wire().Send("GOAL", chapter->key);
    Notify(chapter->name + " complete. Well done, Mr. Freeman.");
}

void WeaponsStripped() { g_stripped = true; }

bool CanEnterVehicle(CBasePlayer* player, CBaseEntity* vehicle) {
    if (player == nullptr || vehicle == nullptr || !Gating()) {
        return true;
    }
    const Chapter* chapter = CurrentChapter();
    const VehicleKey* key = chapter ? Data().KeyFor(chapter->key) : nullptr;
    if (key == nullptr) {
        return true;
    }
    bool keyed = false;
    for (const VehicleClass& known : kVehicleClasses) {
        if (key->vehiclescript == known.script && FClassnameIs(vehicle, known.classname)) {
            keyed = true;
        }
    }
    if (!keyed || Holds(key->item)) {
        return true;
    }
    if (Debounced("vehicle:" + key->item)) {
        Notify("You need " + key->item + " to drive here.");
    }
    return false;
}

CBaseEntity* GrantWeapon(CBasePlayer* player, const char* classname) {
    g_granting = true;
    CBaseEntity* given = player->GiveNamedItem(classname);
    g_granting = false;
    return given;
}

bool GravityGunKill(const CTakeDamageInfo& info) {
    if (!Gating()) {
        return true;  // retail
    }
    CBaseEntity* attacker = info.GetAttacker();
    if (attacker == nullptr || !attacker->IsPlayer() ||
        (info.GetDamageType() & (DMG_PHYSGUN | DMG_CRUSH | DMG_DISSOLVE)) == 0) {
        return false;
    }
    // A ball the gun catches loses its weapon-launched mark; the Pulse
    // Rifle's alt-fire keeps it.
    CPropCombineBall* ball = dynamic_cast<CPropCombineBall*>(info.GetInflictor());
    return ball == nullptr || !ball->WasWeaponLaunched();
}

bool DissolveDroppedWeapon(const CTakeDamageInfo& info) {
    return !Gating() || !Confiscated() || GravityGunKill(info);
}

bool AirboatGunAllowed() { return Holds(kAirboatGunItem); }

void AirboatGunPulled() {
    if (!AirboatGunAllowed() && Debounced("airboat_gun")) {
        Notify("The mounted gun needs the Airboat Gun item.");
    }
}

bool BuggyGunAllowed() {
    return Holds(kBuggyGunItem);
}

void BuggyGunPulled() {
    if (!BuggyGunAllowed() && Debounced("buggy_gun")) {
        Notify("The mounted gun needs the Buggy Gun item.");
    }
}

void MeleeThrowRefused() {
    if (State().OptionBool("melee_throw", false) && Debounced("melee_throw")) {
        Notify("Throwing the crowbar needs the Melee Throw item.");
    }
}

int GravityGunStage() {
    if (!Gating()) {
        return 4;
    }
    return State().Count(kGravityGunItem);
}

void GravityGunRefused(const char* what) {
    if (what != nullptr && Debounced(std::string("physcannon:") + what)) {
        Notify(what);
    }
}

bool SuitPowerAllowed() {
    if (Holds(kSuitItem)) {
        return true;
    }
    if (Debounced("suit_power")) {
        Notify("No aux power until the HEV Suit item arrives.");
    }
    return false;
}

float AuxPowerCap() {
    if (!Gating() || !State().OptionBool("randomize_aux_power", false)) {
        return 100.0f;
    }
    const int stages = (std::min)(State().Count(kAuxPowerItem), kAuxPowerStages);
    return 100.0f * stages / kAuxPowerStages;
}

bool FlashlightAllowed() {
    if (Holds(kFlashlightItem)) {
        return true;
    }
    if (Debounced("flashlight")) {
        Notify("The flashlight needs the Flashlight item.");
    }
    return false;
}

}  // namespace ap

#include "cbase.h"
#include "player.h"
#include "basecombatweapon_shared.h"
#include "ai_basenpc.h"
#include "props.h"
#include "recipientfilter.h"
#include "in_buttons.h"
#include "engine/IEngineSound.h"
#include "weapon_physcannon.h"
#include "ai_network.h"
#include "ai_node.h"
#include "filesystem.h"

#include <algorithm>
#include <cmath>
#include <vector>

#include "ap_traps.h"

#include "ap_bots.h"

#include "ap_checkdata.h"
#include "ap_game.h"
#include "ap_main.h"
#include "ap_state.h"

// memdbgon must be the last include file in a .cpp file!!!
#include "tier0/memdbgon.h"

namespace ap {
namespace {

const char* const kTrapName = "ap_trap";
const char* const kJunkName = "ap_junk";

// --- what traps spawn ---------------------------------------------------------

// NPC Trap: a body and a mind, rolled separately. Every model is a human on
// the shared animation sets, so any of these minds can drive any of them.
// Each in the voice table's order (tools/gen_voice_lines.py).
const char* const kStoryModels[] = {
    "models/gman.mdl",  "models/kleiner.mdl", "models/eli.mdl",
    "models/breen.mdl", "models/mossman.mdl", "models/alyx.mdl",
    "models/barney.mdl", "models/monk.mdl",   "models/odessa.mdl",
};
struct Mind {
    const char* classname;
    bool can_follow;  // a player companion, with a follow behaviour
};
const Mind kMinds[] = {
    {"npc_citizen", true}, {"npc_barney", true},   {"npc_monk", false},
    {"npc_kleiner", false}, {"npc_eli", false},    {"npc_breen", false},
    {"npc_mossman", false}, {"npc_gman", false},
};
enum class Behaviour { kFollow, kWander, kFlee };

// The lines each character has in the game, generated from the voice VPK.
struct VoiceLines {
    const char* const* lines;
    int count;
};
#include "ap_voice_lines.inc"
static_assert(ARRAYSIZE(kVoiceLines) == ARRAYSIZE(kStoryModels),
              "one voice block per story model");

const char* const kOtherClasses[] = {"npc_headcrab", "npc_manhack", "npc_rollermine",
                                     "npc_crow"};

// Junk Trap falls back on these when the map has few loose props of its own.
const char* const kJunkModels[] = {
    "models/props_junk/watermelon01.mdl",
    "models/props_junk/popcan01a.mdl",
    "models/props_junk/garbage_milkcarton002a.mdl",
    "models/props_junk/cardboard_box001a.mdl",
    "models/props_junk/metal_paintcan001a.mdl",
    "models/props_c17/furniturechair001a.mdl",
    "models/props_junk/wood_crate001a.mdl",
    "models/props_junk/plasticbucket001a.mdl",
    "models/props_c17/doll01.mdl",
    "models/props_junk/shoe001a.mdl",
    "models/props_lab/monitor01a.mdl",
    "models/props_c17/metalpot001a.mdl",
    "models/props_junk/trafficcone001a.mdl",
    "models/props_junk/garbage_plasticbottle003a.mdl",
    "models/props_interiors/pot01a.mdl",
    "models/props_junk/glassjug01.mdl",
    "models/props_c17/briefcase001a.mdl",
    "models/props_junk/metalbucket01a.mdl",
    "models/props_lab/huladoll.mdl",
};
const char* const kMapPropClasses[] = {"prop_physics", "prop_physics_multiplayer",
                                       "prop_physics_respawnable", "prop_physics_override"};

const int kNpcCount = 4;
const int kHeadcrabCount = 4;
const int kManhackCount = 4;
const int kRollermineCount = 3;
const int kCrowCount = 12;
const int kJunkCount = 8;
const float kJunkMaxMass = 150.0f;      // kg; a dropped fridge is not junk
const float kJunkFadeSeconds = 60.0f;   // so a pile never blocks a doorway for good
const float kJunkMaxDamage = 5.0f;
const float kButterfingersPickupDelay = 1.0f;  // not caught on the way out
const float kWanderEverySeconds = 3.0f;
const int kNpcHealth = 40;
const int kLinesPerCharacter = 14;        // precached per map, at random
const float kUseReach = 128.0f;
const float kAmbientMin = 25.0f;           // seconds between unprompted lines
const float kAmbientMax = 50.0f;
const float kAmbientRange = 600.0f;

// --- placement ----------------------------------------------------------------
//
// From the HL1 port: each spawn rolls its own bearing and distance, checked
// with traces, so a corridor still gets all of them and nobody arrives inside
// a wall.

struct Hull {
    Vector mins, maxs;
};
const Hull kHumanHull = {Vector(-13, -13, 0), Vector(13, 13, 72)};
const Hull kSmallHull = {Vector(-12, -12, 0), Vector(12, 12, 24)};
const Hull kCrowHull = {Vector(-6, -6, 0), Vector(6, 6, 12)};
const Hull kRollermineHull = {Vector(-16, -16, 0), Vector(16, 16, 32)};
const Hull kFlyerHull = {Vector(-12, -12, -12), Vector(12, 12, 12)};

const int kPlaceAttempts = 10;
const float kWallMargin = 16.0f;
const float kDropHeight = 128.0f;
const float kStepLift = 18.0f;
// The fallback search: from just clear of the player out to this far.
const float kPlayerClearance = 40.0f;
const float kSearchRadius = 1024.0f;
const float kSearchStep = 48.0f;

// Whether a body fits at `at` (feet for floor hulls), on a floor if it needs
// one, clear of the player and of those already placed. `at` is moved down
// onto the floor.
bool Fits(CBasePlayer* player, const Hull& hull, float separation, bool on_floor,
          const std::vector<Vector>& placed, Vector& at) {
    trace_t tr;
    if (on_floor) {
        UTIL_TraceHull(at + Vector(0, 0, kStepLift), at - Vector(0, 0, kDropHeight), hull.mins,
                       hull.maxs, MASK_NPCSOLID, player, COLLISION_GROUP_NONE, &tr);
        if (tr.startsolid || tr.fraction >= 1.0f) {
            return false;  // no floor within reach: a ledge or a shaft
        }
        at = tr.endpos;
    }
    UTIL_TraceHull(at, at, hull.mins, hull.maxs, MASK_NPCSOLID, player, COLLISION_GROUP_NONE,
                   &tr);
    if (tr.startsolid || tr.allsolid) {
        return false;
    }
    // Not on top of the player, whom the traces ignore.
    if ((at - player->GetAbsOrigin()).Length2D() < kPlayerClearance &&
        std::fabs(at.z - player->GetAbsOrigin().z) < 72.0f) {
        return false;
    }
    for (const Vector& other : placed) {
        if ((other - at).Length() < separation) {
            return false;
        }
    }
    return true;
}

// A spot for one spawn. First a random bearing and distance in the ring, as
// the HL1 port; failing that, the nearest spot that fits, searched outward in
// rings (through walls if need be), then the map's AI nodes, nearest first.
// False only when nowhere on the map near enough fits; the caller retries.
bool Place(CBasePlayer* player, const Hull& hull, float min_r, float max_r, float separation,
           bool on_floor, std::vector<Vector>& placed, Vector& spot) {
    const Vector base = on_floor ? player->GetAbsOrigin() + Vector(0, 0, kStepLift)
                                 : player->EyePosition() - Vector(0, 0, 8);
    for (int attempt = 0; attempt < kPlaceAttempts; ++attempt) {
        const float yaw = RandomFloat(0.0f, 360.0f);
        const float dist = RandomFloat(min_r, max_r);
        Vector dir;
        AngleVectors(QAngle(0, yaw, 0), &dir);
        trace_t tr;
        UTIL_TraceHull(base, base + dir * dist, hull.mins, hull.maxs, MASK_NPCSOLID, player,
                       COLLISION_GROUP_NONE, &tr);
        if (tr.startsolid) {
            continue;
        }
        const float reach = dist * tr.fraction - (tr.fraction < 1.0f ? kWallMargin : 0.0f);
        if (reach < min_r * 0.5f) {
            continue;  // a wall in the player's face
        }
        Vector at = base + dir * reach;
        if (on_floor) {
            at.z -= kStepLift;
        }
        if (Fits(player, hull, separation, on_floor, placed, at)) {
            placed.push_back(at);
            spot = at;
            return true;
        }
    }
    // The nearest that fits: rings outward, a start bearing at random so a
    // swarm does not line up, closer ones packed tighter.
    const float tight = (std::min)(separation, hull.maxs.x * 2.0f + 4.0f);
    const float offset = RandomFloat(0.0f, 360.0f);
    for (float r = kPlayerClearance; r <= kSearchRadius; r += kSearchStep) {
        const int bearings = (std::max)(8, static_cast<int>(2.0f * M_PI_F * r / kSearchStep));
        for (int b = 0; b < bearings; ++b) {
            Vector dir;
            AngleVectors(QAngle(0, offset + 360.0f * b / bearings, 0), &dir);
            for (float dz : {0.0f, 64.0f, -64.0f}) {
                Vector at = (on_floor ? player->GetAbsOrigin() : base) + dir * r +
                            Vector(0, 0, dz);
                if (Fits(player, hull, tight, on_floor, placed, at)) {
                    placed.push_back(at);
                    spot = at;
                    return true;
                }
            }
        }
    }
    if (g_pBigAINet != nullptr) {
        std::vector<std::pair<float, Vector>> nodes;
        for (int n = 0; n < g_pBigAINet->NumNodes(); ++n) {
            CAI_Node* node = g_pBigAINet->GetNode(n);
            if (node != nullptr && node->GetType() == NODE_GROUND) {
                const Vector at = node->GetPosition(HULL_HUMAN);
                nodes.push_back({(at - player->GetAbsOrigin()).LengthSqr(), at});
            }
        }
        std::sort(nodes.begin(), nodes.end(),
                  [](const auto& a, const auto& b) { return a.first < b.first; });
        for (const auto& node : nodes) {
            Vector at = node.second + (on_floor ? vec3_origin : Vector(0, 0, 48));
            if (Fits(player, hull, tight, on_floor, placed, at)) {
                placed.push_back(at);
                spot = at;
                return true;
            }
        }
    }
    return false;
}

QAngle Facing(CBasePlayer* player, const Vector& from) {
    QAngle angles;
    VectorAngles(player->GetAbsOrigin() - from, angles);
    return QAngle(0, angles.y, 0);
}

CBaseEntity* SpawnAt(const char* classname, const Vector& at, const QAngle& angles,
                     const std::vector<std::pair<const char*, const char*>>& keys = {}) {
    CBaseEntity* entity = CreateEntityByName(classname);
    if (entity == nullptr) {
        return nullptr;
    }
    for (const auto& kv : keys) {
        entity->KeyValue(kv.first, kv.second);
    }
    entity->SetAbsOrigin(at);
    entity->SetAbsAngles(angles);
    entity->SetName(AllocPooledString(kTrapName));
    if (DispatchSpawn(entity) < 0 || entity->IsMarkedForDeletion()) {
        return nullptr;
    }
    entity->Activate();
    return entity;
}

// Spawns `count` of a class around the player; how many made it.
int SpawnAround(CBasePlayer* player, const char* classname, int count, const Hull& hull,
                float min_r, float max_r, float separation, bool on_floor) {
    std::vector<Vector> placed;
    int made = 0;
    for (int i = 0; i < count; ++i) {
        Vector at;
        if (!Place(player, hull, min_r, max_r, separation, on_floor, placed, at)) {
            break;  // the whole search failed; the rest would too
        }
        if (SpawnAt(classname, at, Facing(player, at)) != nullptr) {
            ++made;
        }
    }
    return made;
}

// --- state ---------------------------------------------------------------------

struct Queued {
    std::string name;
    float wait;  // game seconds left, counted only while the player is up
    // Spawns still owed, for a trap that could not place all of them at once;
    // -1 before it first springs.
    int remaining = -1;
};
std::vector<Queued> g_queue;

// What the NPC Trap made: who wears which character, and what it does.
struct TrapNpc {
    EHANDLE npc;
    int character;
    bool wanders;
    float next_line;
    float busy_until;
};
std::vector<TrapNpc> g_npcs;
// Which story models and fallback junk this install has: a missing model is
// never precached or set.
std::vector<bool> g_storyOnDisk;
std::vector<std::string> g_junkOnDisk;
// This map's precached share of each character's lines.
std::vector<std::vector<const char*>> g_lines;
float g_next_wander = 0.0f;

// Butterfingers.
// Butterfingers: each weapon thrown, on its own clock, any number at once.
struct Drop {
    std::string classname;
    EHANDLE weapon;
    float dropped_at;
};
std::vector<Drop> g_drops;

// Bunny Hop and Sticky Key, on this map's clock.
float g_hop_until = 0.0f;
bool g_jump_down = false;
float g_stuck_until = 0.0f;
const char* g_stuck_key = nullptr;  // "forward", "back", "moveleft", "moveright"
bool g_release_due = false;

struct StuckKey {
    const char* command;
    const char* said;
};
const StuckKey kStuckKeys[] = {
    {"forward", "forward"}, {"back", "back"}, {"moveleft", "strafe left"},
    {"moveright", "strafe right"},
};

// "Shotgun" for weapon_shotgun: the item name where it has one.
std::string ItemNameOf(const std::string& classname) {
    const std::string item = Data().GateOf(classname);
    return item.empty() ? classname.substr(classname.rfind('_') + 1) : item;
}

void PlayerCommand(CBasePlayer* player, const std::string& command) {
    engine->ClientCommand(player->edict(), "%s\n", command.c_str());
}

const Drop* DropOf(CBaseEntity* weapon) {
    for (const Drop& drop : g_drops) {
        if (weapon != nullptr && drop.weapon.Get() == weapon) {
            return &drop;
        }
    }
    return nullptr;
}

// --- the traps -----------------------------------------------------------------

// Spawns up to `want`; how many arrived.
int SpringNpcs(CBasePlayer* player, int want) {
    std::vector<int> characters;
    for (int i = 0; i < ARRAYSIZE(kStoryModels); ++i) {
        if (i < static_cast<int>(g_storyOnDisk.size()) && g_storyOnDisk[i]) {
            characters.push_back(i);
        }
    }
    if (characters.empty()) {
        Notify("NPC Trap: none of the story models are installed.");
        return want;  // owed nothing: no install can ever pay it
    }
    for (size_t i = characters.size(); i > 1; --i) {
        std::swap(characters[i - 1], characters[RandomInt(0, static_cast<int>(i) - 1)]);
    }
    std::vector<Vector> placed;
    int made = 0;
    for (int i = 0; i < want; ++i) {
        Vector at;
        if (!Place(player, kHumanHull, 72.0f, 160.0f, 40.0f, true, placed, at)) {
            break;  // the whole search failed; the rest would too
        }
        const Mind& mind = kMinds[RandomInt(0, ARRAYSIZE(kMinds) - 1)];
        const int character = characters[i % characters.size()];
        const char* model = kStoryModels[character];
        // A unique citizen wears the model it is given; the others are reskinned
        // once they have spawned in their own.
        CBaseEntity* entity = SpawnAt(mind.classname, at, Facing(player, at),
                                      {{"model", model}, {"citizentype", "4"}});
        CAI_BaseNPC* npc = entity ? entity->MyNPCPointer() : nullptr;
        if (npc == nullptr) {
            continue;
        }
        if (Q_stricmp(STRING(npc->GetModelName()), model) != 0) {
            npc->SetModel(model);
            npc->ResetSequenceInfo();
        }
        ++made;
        static int serial = 0;
        const std::string actor = std::string(kTrapName) + "_" + std::to_string(++serial);
        npc->SetName(AllocPooledString(actor.c_str()));
        // Killable, in case one spawns in the way: allies are immune to the
        // player by a capability, the story ones by default.
        npc->CapabilitiesRemove(bits_CAP_FRIENDLY_DMG_IMMUNE);
        npc->m_takedamage = DAMAGE_YES;
        // One health for all: Mossman's 8, with a vital ally's cap of a quarter
        // of it per hit and its regeneration, made her near unkillable.
        npc->SetMaxHealth(kNpcHealth);
        npc->SetHealth(kNpcHealth);
        // Its own AI's chatter would be in the wrong voice; ours speaks instead.
        if (CBaseEntity* filter = CreateEntityByName("ai_speechfilter")) {
            filter->KeyValue("subject", actor.c_str());
            filter->KeyValue("IdleModifier", "0");
            filter->KeyValue("NeverSayHello", "1");
            DispatchSpawn(filter);
            filter->Activate();
        }
        Behaviour behaviour = static_cast<Behaviour>(RandomInt(0, 2));
        if (behaviour == Behaviour::kFollow && !mind.can_follow) {
            behaviour = Behaviour::kWander;
        }
        g_npcs.push_back({npc, character, behaviour == Behaviour::kWander,
                          gpGlobals->curtime + RandomFloat(2.0f, 6.0f), 0.0f});
        if (behaviour == Behaviour::kFollow) {
            // The level designers' way to make a companion follow: a goal entity.
            CBaseEntity* goal = CreateEntityByName("ai_goal_follow");
            if (goal != nullptr) {
                goal->KeyValue("actor", actor.c_str());
                goal->KeyValue("goal", "!player");
                goal->KeyValue("Formation", "0");
                DispatchSpawn(goal);
                goal->Activate();
                variant_t none;
                goal->AcceptInput("Activate", player, player, none, 0);
            }
        } else if (behaviour == Behaviour::kFlee) {
            npc->AddEntityRelationship(player, D_FR, 99);
        }
    }
    return made;
}

int SpringBots(CBasePlayer* player, int want) {
    if (!BotsAvailable()) {
        Notify("Bot Swarm Trap: none of the bot models are installed.");
        return want;  // owed nothing: no install can ever pay it
    }
    std::vector<Vector> placed;
    int made = 0;
    for (int i = 0; i < want; ++i) {
        Vector at;
        if (!Place(player, kHumanHull, 72.0f, 200.0f, 40.0f, true, placed, at)) {
            break;  // the whole search failed; the rest would too
        }
        // Facing the player, so the first thing each runs into is them. One
        // that fails for want of a usable model is not owed: only room is.
        SpawnBot(at, Facing(player, at).y);
        ++made;  // a model that failed was retired (no moves, or a full table)
    }
    return made;
}

void SpringButterfingers(CBasePlayer* player) {
    CBaseCombatWeapon* weapon = player->GetActiveWeapon();
    auto droppable = [](CBaseCombatWeapon* w) {
        if (w == nullptr) {
            return false;
        }
        const char* name = w->GetClassname();
        // A grenade is ammo in the hand; the super gravity gun is the level's.
        return !FClassnameIs(w, "weapon_frag") &&
               !(FClassnameIs(w, "weapon_physcannon") && PlayerHasMegaPhysCannon()) &&
               Q_strncmp(name, "weapon_", 7) == 0;
    };
    if (!droppable(weapon)) {
        weapon = nullptr;
        for (int i = 0; i < player->WeaponCount() && weapon == nullptr; ++i) {
            if (droppable(player->GetWeapon(i))) {
                weapon = player->GetWeapon(i);
            }
        }
    }
    if (weapon == nullptr) {
        Notify("Butterfingers Trap: nothing to drop.");
        return;
    }
    const std::string classname = weapon->GetClassname();
    // A fumble: up and away, somewhere ahead, tumbling. A real physics object,
    // as the thrown crowbar is.
    QAngle aim(-30.0f, player->EyeAngles().y + RandomFloat(-50.0f, 50.0f), 0.0f);
    Vector dir;
    AngleVectors(aim, &dir);
    Vector velocity = dir * 450.0f;
    player->Weapon_Drop(weapon, nullptr, &velocity);
    if (IPhysicsObject* phys = weapon->VPhysicsGetObject()) {
        AngularImpulse spin(RandomFloat(-1500, 1500), RandomFloat(-1500, 1500),
                            RandomFloat(-1500, 1500));
        phys->AddVelocity(nullptr, &spin);
    }
    weapon->Lock(1.0e6f, player);  // the player's to pick up; never an NPC's
    g_drops.push_back({classname, weapon, gpGlobals->curtime});
    if (player->GetActiveWeapon() == nullptr) {
        player->SwitchToNextBestWeapon(nullptr);
    }
    Notify("Butterfingers Trap: you fumbled your " + ItemNameOf(classname) + ".");
}

void SpringBunnyHop() {
    g_hop_until = gpGlobals->curtime + kHeldKeySeconds;
    Notify("Hop, hop, hop!");
}

void SpringStickyKey(CBasePlayer* player) {
    if (g_stuck_key != nullptr) {
        PlayerCommand(player, std::string("-") + g_stuck_key);
    }
    const StuckKey& key = kStuckKeys[RandomInt(0, ARRAYSIZE(kStuckKeys) - 1)];
    g_stuck_key = key.command;
    g_stuck_until = gpGlobals->curtime + kHeldKeySeconds;
    PlayerCommand(player, std::string("+") + key.command);
    Notify(std::string("Sticky Key Trap: ") + key.said + " is stuck down for " +
           std::to_string(static_cast<int>(kHeldKeySeconds)) + " seconds.");
}

void SpringReload(CBasePlayer* player) {
    CBaseCombatWeapon* weapon = player->GetActiveWeapon();
    // The RPG has no magazine: a rocket is loaded from the reserve as it
    // fires. Its reload is the animation, and no firing until it is done.
    if (weapon != nullptr && FClassnameIs(weapon, "weapon_rpg") &&
        player->GetAmmoCount(weapon->GetPrimaryAmmoType()) > 0 && weapon->Reload()) {
        weapon->m_flNextPrimaryAttack = gpGlobals->curtime + weapon->GetViewModelSequenceDuration();
        Notify("Tactical reload!");
        return;
    }
    if (weapon == nullptr || !weapon->UsesClipsForAmmo1() || weapon->Clip1() <= 0 ||
        weapon->GetPrimaryAmmoType() < 0) {
        Notify("Reload Trap: nothing in hand to reload.");
        return;
    }
    // Straight into the reserve, past the carry limit: no ammo is lost.
    const int ammo = weapon->GetPrimaryAmmoType();
    player->SetAmmoCount(player->GetAmmoCount(ammo) + weapon->Clip1(), ammo);
    weapon->m_iClip1 = 0;
    weapon->Reload();
    Notify("Tactical reload!");
}

int SpringJunk(CBasePlayer* player, int want) {
    std::vector<std::string> models = g_junkOnDisk;
    for (const char* cls : kMapPropClasses) {
        for (CBaseEntity* e = gEntList.FindEntityByClassname(nullptr, cls); e != nullptr;
             e = gEntList.FindEntityByClassname(e, cls)) {
            const char* model = STRING(e->GetModelName());
            if (model != nullptr && *model != '\0' &&
                std::find(models.begin(), models.end(), model) == models.end()) {
                models.push_back(model);
            }
        }
    }
    // Under the ceiling, a good way over the player's head.
    const Vector eye = player->EyePosition();
    trace_t tr;
    UTIL_TraceLine(eye, eye + Vector(0, 0, 200), MASK_SOLID, player, COLLISION_GROUP_NONE, &tr);
    const float top = (std::max)(tr.endpos.z - 24.0f, eye.z + 24.0f);
    int made = 0;
    for (int i = 0; i < want; ++i) {
        const Vector above(eye.x, eye.y, top);
        const Vector want = above + Vector(RandomFloat(-64, 64), RandomFloat(-64, 64), 0);
        UTIL_TraceLine(above, want, MASK_SOLID, player, COLLISION_GROUP_NONE, &tr);
        const Vector at = above + (want - above) * (std::max)(tr.fraction - 0.2f, 0.0f);
        for (int tries = 0; tries < 3; ++tries) {
            if (models.empty()) {
                break;
            }
            const std::string& model = models[RandomInt(0, static_cast<int>(models.size()) - 1)];
            CBaseEntity* entity = CreateEntityByName("prop_physics");
            if (entity == nullptr) {
                break;
            }
            entity->KeyValue("model", model.c_str());
            entity->SetAbsOrigin(at);
            entity->SetAbsAngles(QAngle(RandomFloat(0, 360), RandomFloat(0, 360), 0));
            entity->SetName(AllocPooledString(kJunkName));
            if (DispatchSpawn(entity) < 0 || entity->IsMarkedForDeletion()) {
                continue;  // no physics model: not a prop that can fall
            }
            IPhysicsObject* phys = entity->VPhysicsGetObject();
            auto* prop = dynamic_cast<CPhysicsProp*>(entity);
            if (phys == nullptr || phys->GetMass() > kJunkMaxMass ||
                (prop != nullptr && prop->GetExplosiveDamage() > 0.0f)) {
                UTIL_Remove(entity);  // too heavy to be junk, or a barrel that blows up
                continue;
            }
            entity->Activate();
            phys->Wake();
            entity->SUB_StartFadeOut(kJunkFadeSeconds, false);
            ++made;
            break;
        }
    }
    return made;
}

// Whether the trap went off; false leaves it queued for a better moment.
bool Spring(CBasePlayer* player, Queued& queued) {
    const std::string& name = queued.name;
    const bool on_foot = !player->IsInAVehicle();
    // A trap that spawns things never fails for want of room: what could not
    // be placed now stays owed, and the trap is retried shortly for the rest.
    // Announced once, on its first try.
    auto counted = [&](int count, const char* announce, auto spawn) {
        const bool first = queued.remaining < 0;
        const int want = first ? count : queued.remaining;
        if (first) {
            Notify(announce);
        }
        queued.remaining = want - spawn(want);
        return queued.remaining <= 0;
    };
    if (name == "NPC Trap") {
        return counted(kNpcCount, "Company has arrived.",
                       [&](int want) { return SpringNpcs(player, want); });
    } else if (name == "Headcrab Trap") {
        return counted(kHeadcrabCount, "What remarkable specimen!", [&](int want) {
            return SpawnAround(player, "npc_headcrab", want, kSmallHull, 72.0f, 160.0f, 40.0f, true);
        });
    } else if (name == "Manhack Swarm Trap") {
        return counted(kManhackCount, "Manhack Swarm!", [&](int want) {
            return SpawnAround(player, "npc_manhack", want, kFlyerHull, 96.0f, 200.0f, 40.0f, false);
        });
    } else if (name == "Bot Swarm Trap") {
        return counted(kBotSwarmCount, "Bot swarm!",
                       [&](int want) { return SpringBots(player, want); });
    } else if (name == "Mega Bot Swarm Trap") {
        // Test only (not in the apworld): one bot per usable model, each once.
        if (queued.remaining < 0) {
            RefillBotModels();
        }
        return counted(BotModelCount(), "MEGA bot swarm!",
                       [&](int want) { return SpringBots(player, want); });
    } else if (name == "Rollermine Trap") {
        return counted(kRollermineCount, "Rollermine Trap!", [&](int want) {
            return SpawnAround(player, "npc_rollermine", want, kRollermineHull, 96.0f, 200.0f, 48.0f, true);
        });
    } else if (name == "Crow Trap") {
        return counted(kCrowCount, "There's been a murder!", [&](int want) {
            return SpawnAround(player, "npc_crow", want, kCrowHull, 48.0f, 240.0f, 20.0f, true);
        });
    } else if (name == "Junk Trap") {
        return counted(kJunkCount, "Look out!",
                       [&](int want) { return SpringJunk(player, want); });
    } else if (name == "Bunny Hop Trap") {
        SpringBunnyHop();
    } else if (name == "Sticky Key Trap") {
        SpringStickyKey(player);
    } else if (name == "Butterfingers Trap") {
        if (!on_foot) {
            return false;  // nothing in hand in a vehicle
        }
        SpringButterfingers(player);
    } else if (name == "Reload Trap") {
        if (!on_foot) {
            return false;
        }
        SpringReload(player);
    } else {
        Notify("Trap " + name + " is not one this build knows.");
    }
    return true;
}

void RunWithheld(CBasePlayer* player) {
    const bool reissue = State().OptionBool("butterfingers_reissue", true);
    // With reissue off the suit only steps in once the player has nothing
    // left, and then hands back one weapon: the longest gone.
    bool empty_handed = player->WeaponCount() == 0;
    for (size_t i = 0; i < g_drops.size();) {
        Drop& drop = g_drops[i];
        auto* weapon = dynamic_cast<CBaseCombatWeapon*>(drop.weapon.Get());
        if (weapon != nullptr && weapon->GetOwner() == player) {
            g_drops.erase(g_drops.begin() + i);  // picked back up
            continue;
        }
        const bool lost = weapon == nullptr;  // fell out of the world, or dissolved
        const bool due =
            reissue && gpGlobals->curtime - drop.dropped_at >= kButterfingersReturnSeconds;
        if (!lost && !due && !empty_handed) {
            ++i;
            continue;
        }
        empty_handed = false;
        if (weapon != nullptr) {
            UTIL_Remove(weapon);
        }
        Notify("The suit hands back your " + ItemNameOf(drop.classname) + ".");
        g_drops.erase(g_drops.begin() + i);  // the loadout grants it
    }
}

void RunKeys(CBasePlayer* player) {
    if (g_release_due) {
        g_release_due = false;
        PlayerCommand(player, "-jump");
        for (const StuckKey& key : kStuckKeys) {
            PlayerCommand(player, std::string("-") + key.command);
        }
    }
    if (g_hop_until > 0.0f) {
        if (g_jump_down) {
            PlayerCommand(player, "-jump");
            g_jump_down = false;
        } else if (gpGlobals->curtime >= g_hop_until) {
            g_hop_until = 0.0f;
        } else if (player->GetFlags() & FL_ONGROUND) {
            PlayerCommand(player, "+jump");
            g_jump_down = true;
        }
    }
    if (g_stuck_key != nullptr && gpGlobals->curtime >= g_stuck_until) {
        PlayerCommand(player, std::string("-") + g_stuck_key);
        g_stuck_key = nullptr;
    }
}

void Speak(TrapNpc& who, CAI_BaseNPC* npc) {
    if (gpGlobals->curtime < who.busy_until || who.character >= static_cast<int>(g_lines.size()) ||
        g_lines[who.character].empty()) {
        return;
    }
    const auto& lines = g_lines[who.character];
    const char* line = lines[RandomInt(0, static_cast<int>(lines.size()) - 1)];
    CPASAttenuationFilter filter(npc);
    EmitSound_t sound;
    // The second voice channel: the NPC's own AI stops CHAN_VOICE whenever it
    // starts a response (a use, a greeting), which cut these lines off unheard.
    sound.m_nChannel = CHAN_VOICE2;
    sound.m_pSoundName = line;
    sound.m_flVolume = 1.0f;
    sound.m_SoundLevel = SNDLVL_TALKING;
    CBaseEntity::EmitSound(filter, npc->entindex(), sound);
    Msg("[AP] %s (%s) says %s\n", npc->GetClassname(), STRING(npc->GetModelName()), line);
    who.busy_until = gpGlobals->curtime + enginesound->GetSoundDuration(line) + 0.5f;
    who.next_line = who.busy_until + RandomFloat(kAmbientMin, kAmbientMax);
}

// Wanderers keep moving; anyone the player uses, or now and then anyone
// nearby, says one of their lines.
void RunNpcs(CBasePlayer* player) {
    CBaseEntity* used = nullptr;
    if (player->m_afButtonPressed & IN_USE) {
        Vector forward;
        player->EyeVectors(&forward);
        trace_t tr;
        UTIL_TraceLine(player->EyePosition(), player->EyePosition() + forward * kUseReach,
                       MASK_SHOT, player, COLLISION_GROUP_NONE, &tr);
        used = tr.m_pEnt;
    }
    const bool wander_now = gpGlobals->curtime >= g_next_wander;
    if (wander_now) {
        g_next_wander = gpGlobals->curtime + kWanderEverySeconds;
    }
    for (size_t i = 0; i < g_npcs.size();) {
        TrapNpc& who = g_npcs[i];
        CAI_BaseNPC* npc = who.npc ? who.npc->MyNPCPointer() : nullptr;
        if (npc == nullptr || !npc->IsAlive()) {
            g_npcs.erase(g_npcs.begin() + i);
            continue;
        }
        if (used != nullptr && used == npc) {
            Speak(who, npc);
        } else if (gpGlobals->curtime >= who.next_line) {
            if ((npc->GetAbsOrigin() - player->GetAbsOrigin()).Length() < kAmbientRange) {
                Speak(who, npc);
            } else {
                who.next_line = gpGlobals->curtime + RandomFloat(kAmbientMin, kAmbientMax);
            }
        }
        if (wander_now && who.wanders && !npc->IsMoving() &&
            npc->GetState() != NPC_STATE_SCRIPT && npc->GetState() != NPC_STATE_COMBAT) {
            npc->SetSchedule(SCHED_IDLE_WANDER);
        }
        ++i;
    }
}

}  // namespace

void TrapsPrecache() {
    g_storyOnDisk.clear();
    for (const char* model : kStoryModels) {
        const bool present = filesystem->FileExists(model, "GAME");
        g_storyOnDisk.push_back(present && CBaseEntity::PrecacheModel(model) >= 0);
    }
    g_junkOnDisk.clear();
    for (const char* model : kJunkModels) {
        if (filesystem->FileExists(model, "GAME") && CBaseEntity::PrecacheModel(model) >= 0) {
            g_junkOnDisk.push_back(model);
        }
    }
    BotsPrecache();
    for (const Mind& mind : kMinds) {
        UTIL_PrecacheOther(mind.classname);
    }
    // A share of each character's lines, different every map; all of the
    // G-Man's few (his opening among them).
    g_lines.assign(ARRAYSIZE(kVoiceLines), {});
    for (int c = 0; c < ARRAYSIZE(kVoiceLines); ++c) {
        std::vector<const char*> all(kVoiceLines[c].lines,
                                     kVoiceLines[c].lines + kVoiceLines[c].count);
        for (size_t i = all.size(); i > 1; --i) {
            std::swap(all[i - 1], all[RandomInt(0, static_cast<int>(i) - 1)]);
        }
        all.resize((std::min)(all.size(), static_cast<size_t>(kLinesPerCharacter)));
        for (const char* line : all) {
            enginesound->PrecacheSound(line, true);
        }
        g_lines[c] = all;
    }
    for (const char* classname : kOtherClasses) {
        UTIL_PrecacheOther(classname);
    }
}

void TrapsLevelStart() {
    g_drops.clear();
    g_npcs.clear();
    g_next_wander = 0.0f;
    g_release_due = g_hop_until > 0.0f || g_jump_down || g_stuck_key != nullptr || g_release_due;
    g_hop_until = 0.0f;
    g_jump_down = false;
    g_stuck_key = nullptr;
    g_stuck_until = 0.0f;
    for (Queued& queued : g_queue) {
        queued.wait = kTrapDelaySeconds;  // the new level settles first too
    }
}

void QueueTrap(const std::string& name) { g_queue.push_back({name, kTrapDelaySeconds}); }

void TrapsFrame() {
    CBasePlayer* player = Player();
    if (player == nullptr) {
        return;
    }
    RunKeys(player);
    if (!player->IsAlive()) {
        return;
    }
    RunWithheld(player);
    RunNpcs(player);
    for (size_t i = 0; i < g_queue.size();) {
        g_queue[i].wait -= gpGlobals->frametime;
        if (g_queue[i].wait > 0.0f) {
            ++i;
            continue;
        }
        if (Spring(player, g_queue[i])) {
            g_queue.erase(g_queue.begin() + i);
        } else {
            g_queue[i].wait = 2.0f;  // try again shortly, for what is still owed
            ++i;
        }
    }
}

bool Withheld(const std::string& classname) {
    for (const Drop& drop : g_drops) {
        if (drop.classname == classname) {
            return true;
        }
    }
    return false;
}

TrapDrop TrapDropTouched(CBaseEntity* weapon) {
    const Drop* drop = DropOf(weapon);
    if (drop == nullptr) {
        return TrapDrop::kNotTrap;
    }
    if (gpGlobals->curtime - drop->dropped_at < kButterfingersPickupDelay) {
        return TrapDrop::kTooSoon;
    }
    // Not forgotten yet: a touch is not a pickup (the pickup can still fail,
    // say on its visibility check), and forgetting here let the loadout hand
    // a fresh copy over while this one lay there as a weapon to be "found".
    // RunWithheld lets go once the player really holds it.
    return TrapDrop::kTaken;
}

void AdjustPlayerDamage(CBasePlayer* player, CTakeDamageInfo& info) {
    CBaseEntity* inflictor = info.GetInflictor();
    CBaseEntity* attacker = info.GetAttacker();
    const bool junk = (inflictor != nullptr && inflictor->NameMatches(kJunkName)) ||
                      (attacker != nullptr && attacker->NameMatches(kJunkName));
    if (!junk || player == nullptr) {
        return;
    }
    float damage = (std::min)(info.GetDamage(), kJunkMaxDamage);
    damage = (std::min)(damage, static_cast<float>((std::max)(player->GetHealth() - 1, 0)));
    info.SetDamage(damage);
}

}  // namespace ap

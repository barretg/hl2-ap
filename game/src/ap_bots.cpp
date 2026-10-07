#include "cbase.h"
#include "ai_basenpc.h"
#include "ai_motor.h"
#include "filesystem.h"
#include "networkstringtable_gamedll.h"
#include "player.h"
#include "takedamageinfo.h"

#include <algorithm>
#include <cmath>
#include <vector>

#include "ap_bots.h"

#include "ap_main.h"

// memdbgon must be the last include file in a .cpp file!!!
#include "tier0/memdbgon.h"

namespace {

// --- the brain's numbers, from the HL1 port (fun-with-bots) --------------------

// How far ahead the way is checked, how often progress is sampled, and how far
// the bot must have gone in that time to count as moving.
constexpr float kLookahead = 24.0f;
constexpr float kProgressInterval = 0.3f;
constexpr float kProgressDistance = 16.0f;
constexpr float kStepHeight = 18.0f;

// A jump got somewhere if it ended this much higher or further along; one not
// landed by the timeout was a fall.
constexpr float kJumpGainZ = 8.0f;
constexpr float kJumpGainForward = 16.0f;
constexpr float kJumpTimeout = 2.0f;

// The smallest turn when a heading is given up on.
constexpr float kTurnMin = 45.0f;

// Reach, the swing's timing, and the bout: 1 to 3 swings, then run off.
constexpr float kMeleeRange = 48.0f;
constexpr float kMeleeHeight = 72.0f;
constexpr float kSwingHitAt = 0.2f;
constexpr float kSwingTime = 0.55f;
constexpr float kRecoverTime = 0.2f;
constexpr int kBoutSwingsMin = 1;
constexpr int kBoutSwingsMax = 3;
constexpr float kFleeMinSeconds = 1.0f;
constexpr float kFleeMaxSeconds = 2.0f;
constexpr float kFleeSpread = 45.0f;

// A player's run, and HL1's jump (about 60 units at HL2's gravity).
constexpr float kRunSpeed = 240.0f;
constexpr float kJumpSpeed = 268.0f;

constexpr float kThinkInterval = 0.05f;

// --- the bodies ----------------------------------------------------------------

// Every biped HL2 ships with a run or walk of its own. The animations are looked
// up by activity on the model at spawn, so families on different skeletons
// (Combine, vortigaunts, zombies) all work; one with nothing to move with is
// passed over. Only those found on disk are precached: a missing model is never
// precached or set, so an incomplete install costs variety, not a crash.
const char* const kBotModels[] = {
    "models/alyx.mdl", "models/barney.mdl", "models/breen.mdl", "models/eli.mdl",
    "models/gman_high.mdl", "models/kleiner.mdl", "models/monk.mdl", "models/mossman.mdl",
    "models/odessa.mdl", "models/police.mdl", "models/combine_soldier.mdl",
    "models/combine_soldier_prisonguard.mdl", "models/combine_super_soldier.mdl",
    "models/stalker.mdl", "models/vortigaunt.mdl", "models/vortigaunt_slave.mdl",
    "models/zombie/classic.mdl", "models/zombie/fast.mdl", "models/zombie/poison.mdl",
    "models/humans/group01/male_01.mdl", "models/humans/group01/male_02.mdl",
    "models/humans/group01/male_03.mdl", "models/humans/group01/male_04.mdl",
    "models/humans/group01/male_05.mdl", "models/humans/group01/male_06.mdl",
    "models/humans/group01/male_07.mdl", "models/humans/group01/male_08.mdl",
    "models/humans/group01/male_09.mdl", "models/humans/group01/female_01.mdl",
    "models/humans/group01/female_02.mdl", "models/humans/group01/female_03.mdl",
    "models/humans/group01/female_04.mdl", "models/humans/group01/female_06.mdl",
    "models/humans/group01/female_07.mdl", "models/humans/group02/male_01.mdl",
    "models/humans/group02/male_02.mdl", "models/humans/group02/male_03.mdl",
    "models/humans/group02/male_04.mdl", "models/humans/group02/male_05.mdl",
    "models/humans/group02/male_06.mdl", "models/humans/group02/male_07.mdl",
    "models/humans/group02/male_08.mdl", "models/humans/group02/male_09.mdl",
    "models/humans/group02/female_01.mdl", "models/humans/group02/female_02.mdl",
    "models/humans/group02/female_03.mdl", "models/humans/group02/female_04.mdl",
    "models/humans/group02/female_06.mdl", "models/humans/group02/female_07.mdl",
    "models/humans/group03/male_01.mdl", "models/humans/group03/male_02.mdl",
    "models/humans/group03/male_03.mdl", "models/humans/group03/male_04.mdl",
    "models/humans/group03/male_05.mdl", "models/humans/group03/male_06.mdl",
    "models/humans/group03/male_07.mdl", "models/humans/group03/male_08.mdl",
    "models/humans/group03/male_09.mdl", "models/humans/group03/female_01.mdl",
    "models/humans/group03/female_02.mdl", "models/humans/group03/female_03.mdl",
    "models/humans/group03/female_04.mdl", "models/humans/group03/female_06.mdl",
    "models/humans/group03/female_07.mdl", "models/humans/group03/male_01_bloody.mdl",
    "models/humans/group03/male_05_bloody.mdl", "models/humans/group03/female_02_bloody.mdl",
    "models/humans/group03m/male_01.mdl", "models/humans/group03m/male_04.mdl",
    "models/humans/group03m/male_07.mdl", "models/humans/group03m/female_01.mdl",
    "models/humans/group03m/female_04.mdl",
};

// Every model on disk is in play. Each is precached the first time a bot
// wears it rather than at map load, so a map where the trap never springs
// pays nothing for them. Bots draw from a shuffled bag, so a model comes up
// again only once all the others have.
std::vector<const char*> g_present;
std::vector<const char*> g_bag;

const char* NextModel() {
    if (g_bag.empty()) {
        g_bag = g_present;
        for (size_t i = g_bag.size(); i > 1; --i) {
            std::swap(g_bag[i - 1], g_bag[RandomInt(0, static_cast<int>(i) - 1)]);
        }
    }
    if (g_bag.empty()) {
        return nullptr;
    }
    const char* model = g_bag.back();
    g_bag.pop_back();
    return model;
}

// Never asked of this model again (no animation to move with, or no room left
// in the precache table).
void Retire(const char* model) {
    g_present.erase(std::remove(g_present.begin(), g_present.end(), model), g_present.end());
    g_bag.erase(std::remove(g_bag.begin(), g_bag.end(), model), g_bag.end());
}

const char* const kCrowbarModel = "models/weapons/w_crowbar.mdl";
bool g_crowbarModel = false;
// The crowbar's one bone, merged onto the bot's own: every ValveBiped model
// has it. The hand attachment narrows that to the models that hold weapons
// (humans, Combine); zombies share the skeleton but swing their claws.
const char* const kHandBone = "ValveBiped.Bip01_R_Hand";
const char* const kHandAttachment = "anim_attachment_RH";

const char* const kSoundMiss = "Weapon_Crowbar.Single";
const char* const kSoundHitBody = "Weapon_Crowbar.Melee_Hit";
const char* const kSoundHitWorld = "Weapon_Crowbar.Melee_HitWorld";

bool OnDisk(const char* model) { return filesystem->FileExists(model, "GAME"); }

// Precaches a model mid-map only with room to spare: a full model table is a
// fatal engine error, not a failed call. Already-precached models are free.
constexpr int kModelTableMargin = 64;
bool PrecacheSafely(const char* model) {
    INetworkStringTable* table =
        networkstringtable ? networkstringtable->FindTable("modelprecache") : nullptr;
    if (table == nullptr) {
        return false;
    }
    if (table->FindStringIndex(model) == INVALID_STRING_INDEX &&
        table->GetNumStrings() >= table->GetMaxStrings() - kModelTableMargin) {
        return false;
    }
    return CBaseEntity::PrecacheModel(model) >= 0;
}

// The first of `acts` this model has, or -1.
template <size_t N>
int FirstSequence(CBaseAnimating* body, const Activity (&acts)[N]) {
    for (Activity act : acts) {
        const int seq = body->SelectWeightedSequence(act);
        if (seq != ACTIVITY_NOT_AVAILABLE) {
            return seq;
        }
    }
    return -1;
}

enum MoveState { kMoveWander, kMoveJump };
enum MeleeState { kMeleeIdle, kMeleeSwing, kMeleeRecover };

}  // namespace

class CApBot : public CAI_BaseNPC {
    DECLARE_CLASS(CApBot, CAI_BaseNPC);
    DECLARE_DATADESC();

public:
    void Spawn() override;
    void Precache() override;
    Class_T Classify() override { return CLASS_NONE; }
    void NPCThink() override;
    void Event_Killed(const CTakeDamageInfo& info) override;
    void UpdateOnRemove() override;

private:
    bool OnGround() const { return (GetFlags() & FL_ONGROUND) != 0; }
    Vector Eyes() const { return GetAbsOrigin() + Vector(0, 0, 64); }
    bool PathClear(const Vector& forward);
    void ResolveSequences();
    void PlaySequence(int seq, bool restart, float rate = 1.0f);
    void EnsureCrowbar();
    void DropCrowbar();
    void TurnAway();
    void SampleProgress();
    CBaseEntity* FindVictim();
    void Swing(CBaseEntity* victim);
    bool MeleeThink(float& yaw);
    void JumpThink(const Vector& forward);
    void Walk(float yaw, float distance);
    void MoveThink(float dt, float yaw, bool fighting);
    void Animate(bool moving);

    // Saved: which crowbar is this bot's, so a restore does not make a second.
    EHANDLE m_crowbar;

    // Not saved: a restored bot starts its brain and its animations over.
    bool m_resolved = false;
    int m_seqIdle = -1, m_seqMove = -1, m_seqJump = -1, m_seqSwing = -1;
    float m_yaw = 0.0f;
    float m_lastThink = 0.0f;
    MoveState m_move = kMoveWander;
    Vector m_lastOrigin;
    float m_nextProgressCheck = 0.0f;
    Vector m_jumpStart;
    bool m_airborne = false;
    float m_jumpExpire = 0.0f;
    MeleeState m_melee = kMeleeIdle;
    float m_meleeNext = 0.0f;
    bool m_hitPending = false;
    int m_swingsLeft = 0;
};

LINK_ENTITY_TO_CLASS(ap_bot, CApBot);

BEGIN_DATADESC(CApBot)
    DEFINE_FIELD(m_crowbar, FIELD_EHANDLE),
END_DATADESC()

void CApBot::Precache() {
    // The model is chosen and precached before spawn (ap::SpawnBot); this is
    // only for a restore, which brings its own.
    PrecacheModel(STRING(GetModelName()));
    BaseClass::Precache();
}

void CApBot::Spawn() {
    Precache();
    SetModel(STRING(GetModelName()));
    SetHullType(HULL_HUMAN);
    SetHullSizeNormal();
    SetSolid(SOLID_BBOX);
    AddSolidFlags(FSOLID_NOT_STANDABLE);
    SetMoveType(MOVETYPE_STEP);
    SetBloodColor(BLOOD_COLOR_RED);
    m_iHealth = ap::kBotHealth;
    m_iMaxHealth = ap::kBotHealth;
    m_flFieldOfView = 0.5f;
    m_NPCState = NPC_STATE_NONE;
    CapabilitiesClear();
    CapabilitiesAdd(bits_CAP_MOVE_GROUND);
    NPCInit();

    m_yaw = GetAbsAngles().y;
    SampleProgress();
    ResolveSequences();
    // Staggered, so a swarm does not think in lockstep.
    SetNextThink(gpGlobals->curtime + RandomFloat(0.05f, 0.15f));
}

void CApBot::ResolveSequences() {
    m_resolved = true;
    static const Activity kIdle[] = {ACT_IDLE_ANGRY_MELEE, ACT_IDLE, ACT_IDLE_ANGRY};
    static const Activity kMove[] = {ACT_RUN, ACT_RUN_RIFLE, ACT_RUN_AIM_RIFLE, ACT_WALK,
                                     ACT_WALK_RIFLE};
    static const Activity kJump[] = {ACT_JUMP, ACT_GLIDE};
    static const Activity kSwing[] = {ACT_MELEE_ATTACK_SWING, ACT_MELEE_ATTACK1,
                                      ACT_MELEE_ATTACK2};
    m_seqIdle = FirstSequence(this, kIdle);
    m_seqMove = FirstSequence(this, kMove);
    m_seqJump = FirstSequence(this, kJump);
    m_seqSwing = FirstSequence(this, kSwing);
    PlaySequence(m_seqIdle, true);
}

void CApBot::PlaySequence(int seq, bool restart, float rate) {
    if (seq < 0) {
        return;
    }
    if (restart || GetSequence() != seq) {
        ResetSequence(seq);
    }
    SetPlaybackRate(rate);
}

// A bonemerged crowbar: an NPC's world weapon is held the same way.
void CApBot::EnsureCrowbar() {
    if (m_crowbar != nullptr || !g_crowbarModel || LookupBone(kHandBone) < 0 ||
        LookupAttachment(kHandAttachment) <= 0) {
        return;
    }
    CBaseEntity* crowbar = CreateEntityByName("prop_dynamic_override");
    if (crowbar == nullptr) {
        return;
    }
    crowbar->KeyValue("model", kCrowbarModel);
    crowbar->KeyValue("solid", "0");
    crowbar->SetAbsOrigin(GetAbsOrigin());
    if (DispatchSpawn(crowbar) < 0 || crowbar->IsMarkedForDeletion()) {
        return;
    }
    crowbar->FollowEntity(this, true);
    m_crowbar = crowbar;
}

void CApBot::DropCrowbar() {
    if (CBaseEntity* crowbar = m_crowbar.Get()) {
        UTIL_Remove(crowbar);
    }
    m_crowbar = nullptr;
}

void CApBot::UpdateOnRemove() {
    DropCrowbar();
    BaseClass::UpdateOnRemove();
}

void CApBot::SampleProgress() {
    m_lastOrigin = GetAbsOrigin();
    m_nextProgressCheck = gpGlobals->curtime + kProgressInterval;
}

void CApBot::TurnAway() {
    const float turn = RandomFloat(kTurnMin, 180.0f);
    m_yaw = UTIL_AngleMod(m_yaw + (RandomInt(0, 1) ? turn : -turn));
    SampleProgress();
}

// Room to go kLookahead units along `forward`: flat first, then from the top of
// a step, which the motor walks the bot up anyway.
bool CApBot::PathClear(const Vector& forward) {
    for (int pass = 0; pass < 2; ++pass) {
        const Vector start = GetAbsOrigin() + Vector(0, 0, 1.0f + (pass ? kStepHeight : 0.0f));
        trace_t tr;
        UTIL_TraceHull(start, start + forward * kLookahead, WorldAlignMins(), WorldAlignMaxs(),
                       MASK_NPCSOLID, this, COLLISION_GROUP_NONE, &tr);
        if (!tr.startsolid && !tr.allsolid && tr.fraction == 1.0f) {
            return true;
        }
    }
    return false;
}

// Whatever this bot has run into: anyone alive in reach (the player, an NPC,
// another bot), else whatever breakable thing is straight ahead.
CBaseEntity* CApBot::FindVictim() {
    const Vector eyes = Eyes();
    CBaseEntity* nearest = nullptr;
    float nearest_distance = kMeleeRange;
    CBaseEntity* list[64];
    const int count = UTIL_EntitiesInSphere(list, ARRAYSIZE(list), GetAbsOrigin(),
                                            kMeleeRange + kMeleeHeight, 0);
    for (int i = 0; i < count; ++i) {
        CBaseEntity* other = list[i];
        if (other == this || other->m_takedamage == DAMAGE_NO || !other->IsAlive()) {
            continue;
        }
        if ((!other->IsPlayer() && other->MyNPCPointer() == nullptr) ||
            (other->GetFlags() & FL_NOTARGET) != 0) {
            continue;
        }
        const Vector delta = other->GetAbsOrigin() - GetAbsOrigin();
        if (std::fabs(delta.z) > kMeleeHeight) {
            continue;
        }
        const float distance = delta.Length2D();
        if (distance > nearest_distance) {
            continue;
        }
        trace_t tr;
        UTIL_TraceLine(eyes, other->WorldSpaceCenter(), MASK_SOLID_BRUSHONLY, this,
                       COLLISION_GROUP_NONE, &tr);
        if (tr.fraction < 1.0f) {
            continue;  // not through a wall
        }
        nearest_distance = distance;
        nearest = other;
    }
    if (nearest != nullptr) {
        return nearest;
    }
    Vector forward;
    AngleVectors(QAngle(0, m_yaw, 0), &forward);
    trace_t tr;
    UTIL_TraceLine(eyes, eyes + forward * kMeleeRange, MASK_SHOT, this, COLLISION_GROUP_NONE,
                   &tr);
    CBaseEntity* hit = tr.m_pEnt;
    if (tr.fraction < 1.0f && hit != nullptr && !hit->IsWorld() && hit != this &&
        hit->m_takedamage != DAMAGE_NO) {
        return hit;
    }
    return nullptr;
}

// The crowbar's swing from a bot: a short line at the victim, then a small hull
// if the line slipped past.
void CApBot::Swing(CBaseEntity* victim) {
    const Vector eyes = Eyes();
    Vector direction;
    if (victim != nullptr) {
        direction = victim->WorldSpaceCenter() - eyes;
        VectorNormalize(direction);
    } else {
        AngleVectors(QAngle(0, m_yaw, 0), &direction);
    }
    const Vector end = eyes + direction * (kMeleeRange + 16.0f);
    trace_t tr;
    UTIL_TraceLine(eyes, end, MASK_SHOT_HULL, this, COLLISION_GROUP_NONE, &tr);
    if (tr.fraction >= 1.0f) {
        UTIL_TraceHull(eyes, end, Vector(-16, -16, -16), Vector(16, 16, 16), MASK_SHOT_HULL,
                       this, COLLISION_GROUP_NONE, &tr);
    }
    CBaseEntity* hit = tr.fraction < 1.0f ? tr.m_pEnt : nullptr;
    if (hit == nullptr) {
        EmitSound(kSoundMiss);
        return;
    }
    CTakeDamageInfo info(this, this, ap::kBotCrowbarDamage, DMG_CLUB);
    CalculateMeleeDamageForce(&info, direction, tr.endpos);
    ClearMultiDamage();
    hit->DispatchTraceAttack(info, direction, &tr);
    ApplyMultiDamage();
    EmitSound(hit->IsPlayer() || hit->MyNPCPointer() != nullptr ? kSoundHitBody
                                                                : kSoundHitWorld);
}

// True while a swing is in progress. `yaw` turns to face the victim; the heading
// is left alone, so the bot carries on its way after.
bool CApBot::MeleeThink(float& yaw) {
    CBaseEntity* victim = FindVictim();
    if (m_melee == kMeleeIdle) {
        if (victim == nullptr || gpGlobals->curtime < m_meleeNext) {
            return false;
        }
        if (m_swingsLeft <= 0) {
            m_swingsLeft = RandomInt(kBoutSwingsMin, kBoutSwingsMax);
        }
        m_melee = kMeleeSwing;
        m_meleeNext = gpGlobals->curtime + kSwingTime;
        m_hitPending = true;
        // The whole swing animation, fitted to the swing's time.
        const float duration = m_seqSwing >= 0 ? SequenceDuration(m_seqSwing) : 0.0f;
        PlaySequence(m_seqSwing >= 0 ? m_seqSwing : m_seqIdle, true,
                     duration > 0.0f ? clamp(duration / kSwingTime, 0.5f, 3.0f) : 1.0f);
    }
    if (victim != nullptr) {
        yaw = UTIL_VecToYaw(victim->GetAbsOrigin() - GetAbsOrigin());
    }
    switch (m_melee) {
        case kMeleeSwing:
            if (m_hitPending && gpGlobals->curtime >= m_meleeNext - kSwingTime + kSwingHitAt) {
                m_hitPending = false;
                SetAbsAngles(QAngle(0, yaw, 0));
                Swing(victim);
                --m_swingsLeft;
            }
            if (gpGlobals->curtime >= m_meleeNext) {
                m_melee = kMeleeRecover;
                m_meleeNext = gpGlobals->curtime + kRecoverTime;
            }
            break;
        case kMeleeRecover:
            if (gpGlobals->curtime >= m_meleeNext) {
                m_melee = kMeleeIdle;
                m_meleeNext = gpGlobals->curtime;
                if (victim == nullptr) {
                    m_swingsLeft = 0;  // it left first; the next bump is a new bout
                    return false;
                }
                if (m_swingsLeft > 0) {
                    return true;  // straight into the next swing
                }
                // Bout over: turn tail, and leave everything alone until clear.
                m_swingsLeft = 0;
                m_yaw = UTIL_AngleMod(UTIL_VecToYaw(GetAbsOrigin() - victim->GetAbsOrigin()) +
                                      RandomFloat(-kFleeSpread, kFleeSpread));
                m_meleeNext = gpGlobals->curtime + RandomFloat(kFleeMinSeconds, kFleeMaxSeconds);
                SampleProgress();
                return false;
            }
            break;
        default:
            break;
    }
    return m_melee != kMeleeIdle;
}

void CApBot::JumpThink(const Vector& forward) {
    // On the ground as well as in the air: a jump that never left the ground is
    // somewhere a jump does not work.
    if (gpGlobals->curtime >= m_jumpExpire) {
        m_move = kMoveWander;
        m_airborne = false;
        TurnAway();
        return;
    }
    if (!m_airborne) {
        m_airborne = !OnGround();
        return;
    }
    if (OnGround()) {
        const Vector travel = GetAbsOrigin() - m_jumpStart;
        const bool gained = travel.z > kJumpGainZ || DotProduct(travel, forward) > kJumpGainForward;
        m_move = kMoveWander;
        m_airborne = false;
        SampleProgress();
        if (!gained) {
            TurnAway();
        }
    }
}

// One step along `yaw` by the NPC motor, which climbs steps and keeps the bot
// on the floor; it stops at ledges rather than walking off them.
void CApBot::Walk(float yaw, float distance) {
    Vector forward;
    AngleVectors(QAngle(0, yaw, 0), &forward);
    AIMoveTrace_t trace;
    GetMotor()->MoveGroundStep(GetAbsOrigin() + forward * distance, nullptr, -1, true, true,
                               &trace);
}

void CApBot::MoveThink(float dt, float yaw, bool fighting) {
    Vector forward;
    AngleVectors(QAngle(0, m_yaw, 0), &forward);
    if (m_move == kMoveJump) {
        JumpThink(forward);
        return;
    }
    if (!OnGround()) {
        return;  // falling; the step physics has it
    }
    if (fighting) {
        // Into whoever is being hit; standing still to hit them is not stuck.
        Walk(yaw, kRunSpeed * dt);
        SampleProgress();
        return;
    }
    // The trace sees a wall before the bot is against it; the progress sample
    // catches what the trace cannot (a corner, a ledge, someone in the way).
    bool stuck = false;
    if (gpGlobals->curtime >= m_nextProgressCheck) {
        stuck = (GetAbsOrigin() - m_lastOrigin).Length2D() < kProgressDistance;
        SampleProgress();
    }
    if (!stuck && PathClear(forward)) {
        Walk(m_yaw, kRunSpeed * dt);
        return;
    }
    // Jump it, and let the landing judge the heading.
    m_move = kMoveJump;
    m_jumpStart = GetAbsOrigin();
    m_airborne = false;
    m_jumpExpire = gpGlobals->curtime + kJumpTimeout;
    SetGroundEntity(nullptr);
    SetAbsOrigin(GetAbsOrigin() + Vector(0, 0, 1));
    SetAbsVelocity(forward * kRunSpeed + Vector(0, 0, kJumpSpeed));
}

void CApBot::Animate(bool moving) {
    if (m_melee != kMeleeIdle) {
        return;  // the swing owns the animation until it is done
    }
    if (!OnGround() || m_move == kMoveJump) {
        PlaySequence(m_seqJump >= 0 ? m_seqJump : m_seqMove, false);
    } else if (moving && m_seqMove >= 0) {
        // Played at the speed the bot actually goes, so the feet keep up.
        const float ground = GetSequenceGroundSpeed(m_seqMove);
        PlaySequence(m_seqMove, false,
                     ground > 1.0f ? clamp(kRunSpeed / ground, 0.5f, 3.0f) : 1.0f);
    } else {
        PlaySequence(m_seqIdle, false);
    }
}

void CApBot::NPCThink() {
    SetNextThink(gpGlobals->curtime + kThinkInterval);
    if (!IsAlive()) {
        return;
    }
    if (!m_resolved) {
        ResolveSequences();  // restored from a save
    }
    float dt = gpGlobals->curtime - m_lastThink;
    if (m_lastThink <= 0.0f || dt < 0.0f || dt > 0.2f) {
        dt = kThinkInterval;
    }
    m_lastThink = gpGlobals->curtime;

    EnsureCrowbar();
    StudioFrameAdvance();

    float yaw = m_yaw;
    const bool fighting = MeleeThink(yaw);
    if (fighting && m_move == kMoveJump && OnGround()) {
        m_move = kMoveWander;  // the fight matters more than the obstacle
        m_airborne = false;
    }
    MoveThink(dt, yaw, fighting);
    SetAbsAngles(QAngle(0, fighting ? yaw : m_yaw, 0));
    Animate(!fighting);
}

void CApBot::Event_Killed(const CTakeDamageInfo& info) {
    DropCrowbar();
    BaseClass::Event_Killed(info);
    // A ragdoll is the client's; the brain stops. A model with no ragdoll goes
    // away rather than standing there dead.
    if (!CanBecomeRagdoll() && !IsMarkedForDeletion()) {
        SUB_StartFadeOut(1.0f, false);
    }
}

namespace ap {

void BotsPrecache() {
    g_present.clear();
    g_bag.clear();
    for (const char* model : kBotModels) {
        if (OnDisk(model)) {
            g_present.push_back(model);
        }
    }
    g_crowbarModel = OnDisk(kCrowbarModel) && CBaseEntity::PrecacheModel(kCrowbarModel) >= 0;
    CBaseEntity::PrecacheScriptSound(kSoundMiss);
    CBaseEntity::PrecacheScriptSound(kSoundHitBody);
    CBaseEntity::PrecacheScriptSound(kSoundHitWorld);
    UTIL_PrecacheOther("prop_dynamic_override");
}

bool BotsAvailable() { return !g_present.empty(); }

int BotModelCount() { return static_cast<int>(g_present.size()); }

void RefillBotModels() { g_bag.clear(); }

CBaseEntity* SpawnBot(const Vector& feet, float yaw) {
    // A model with nothing to move with is passed over; a few tries for one
    // that has.
    for (int attempt = 0; attempt < 4; ++attempt) {
        const char* model = NextModel();
        if (model == nullptr) {
            return nullptr;
        }
        // On disk (checked at map load); refused only near a full table.
        if (!PrecacheSafely(model)) {
            Retire(model);
            continue;
        }
        CApBot* bot = dynamic_cast<CApBot*>(CreateEntityByName("ap_bot"));
        if (bot == nullptr) {
            return nullptr;
        }
        bot->SetModelName(AllocPooledString(model));
        bot->SetAbsOrigin(feet);
        bot->SetAbsAngles(QAngle(0, UTIL_AngleMod(yaw), 0));
        if (DispatchSpawn(bot) < 0 || bot->IsMarkedForDeletion()) {
            continue;
        }
        if (bot->SelectWeightedSequence(ACT_RUN) == ACTIVITY_NOT_AVAILABLE &&
            bot->SelectWeightedSequence(ACT_RUN_RIFLE) == ACTIVITY_NOT_AVAILABLE &&
            bot->SelectWeightedSequence(ACT_WALK) == ACTIVITY_NOT_AVAILABLE &&
            bot->SelectWeightedSequence(ACT_WALK_RIFLE) == ACTIVITY_NOT_AVAILABLE) {
            UTIL_Remove(bot);
            Retire(model);
            continue;
        }
        bot->Activate();
        return bot;
    }
    return nullptr;
}

}  // namespace ap

#include "cbase.h"
#include "player.h"
#include "basecombatweapon_shared.h"
#include "physics.h"

#include "ap_melee.h"

#include "ap_game.h"
#include "ap_main.h"
#include "ap_state.h"

// memdbgon must be the last include file in a .cpp file!!!
#include "tier0/memdbgon.h"

namespace {

const char* const kThrownClass = "ap_thrown_crowbar";
const char* const kModel = "models/weapons/w_crowbar.mdl";
const char* const kMeleeThrowItem = "Melee Throw";
const float kSpeed = 1100.0f;
const float kLift = 100.0f;
const float kGravity = 0.6f;
const float kDamage = 40.0f;      // four crowbar swings (sk_plr_dmg_crowbar 10)
const float kReturnSeconds = 10.0f;
const float kPickupDelay = 0.5f;  // never caught on the way out

// Murder (gmod) mu_knife physics: a real VPhysics object launched at
// aim * (charge * 1000 + 200), spun about its local Y axis, hurting only on its
// first collision. Charge is fixed at Murder's no-charge-bar value.
const float kPhysCharge = 0.6f;
const float kPhysSpin = 1500.0f;      // degrees/s
const float kPhysPitchUp = -28.0f;
const float kPhysThink = 0.1f;
const float kPhysCatchRadius = 48.0f;

ConVar ap_crowbar_throw_style("ap_crowbar_throw_style", "1", FCVAR_NONE,
                              "Crowbar throw: 0 scripted flight, 1 Murder-style physics (test)");

}  // namespace

class CAPThrownCrowbar : public CBaseAnimating {
public:
    DECLARE_CLASS(CAPThrownCrowbar, CBaseAnimating);
    DECLARE_DATADESC();

    void Precache() override {
        PrecacheModel(kModel);
        PrecacheScriptSound("Weapon_Crowbar.Melee_Hit");
        PrecacheScriptSound("Weapon_Crowbar.Single");
    }

    void Spawn() override {
        Precache();
        SetModel(kModel);
        m_flThrown = gpGlobals->curtime;
        m_bFlying = true;
        if (m_bPhysics) {
            SetSolid(SOLID_VPHYSICS);
            if (VPhysicsInitNormal(SOLID_VPHYSICS, 0, false) == nullptr) {
                m_bPhysics = false;  // no collision model: fall back to the scripted throw
            } else {
                SetThink(&CAPThrownCrowbar::PhysicsThink);
                SetNextThink(gpGlobals->curtime + kPhysThink);
                return;
            }
        }
        SetMoveType(MOVETYPE_FLYGRAVITY, MOVECOLLIDE_FLY_CUSTOM);
        SetSolid(SOLID_BBOX);
        AddSolidFlags(FSOLID_TRIGGER | FSOLID_NOT_STANDABLE);
        UTIL_SetSize(this, Vector(-4, -4, -4), Vector(4, 4, 4));
        SetGravity(kGravity);
        SetLocalAngularVelocity(QAngle(-900, 0, 0));
        SetTouch(&CAPThrownCrowbar::CrowbarTouch);
        SetThink(&CAPThrownCrowbar::ReturnThink);
        SetNextThink(gpGlobals->curtime + kReturnSeconds);
    }

    void UsePhysics() { m_bPhysics = true; }
    bool UsingPhysics() const { return m_bPhysics; }

    // The first collision hurts what it hits, then the crowbar just tumbles.
    void VPhysicsCollision(int index, gamevcollisionevent_t* pEvent) override {
        BaseClass::VPhysicsCollision(index, pEvent);
        if (!m_bFlying) {
            return;
        }
        CBaseEntity* other = pEvent->pEntities[!index];
        if (other != nullptr && other->IsPlayer()) {
            return;  // brushing the thrower on release is not a hit
        }
        m_bFlying = false;
        if (other == nullptr || other->m_takedamage == DAMAGE_NO) {
            return;
        }
        CBasePlayer* thrower = ToBasePlayer(GetOwnerEntity());
        Vector pos;
        pEvent->pInternalData->GetContactPoint(pos);
        CTakeDamageInfo info(this, thrower ? static_cast<CBaseEntity*>(thrower) : this,
                             kDamage, DMG_CLUB);
        CalculateMeleeDamageForce(&info, pEvent->preVelocity[index], pos);
        PhysCallbackDamage(other, info, *pEvent, !index);
        EmitSound("Weapon_Crowbar.Melee_Hit");
    }

    // Murder's knife becomes a pickup once it settles; here walking over it,
    // or meeting it in the air after the pickup delay, returns it.
    void PhysicsThink() {
        if (gpGlobals->curtime - m_flThrown > kReturnSeconds) {
            Return();
            return;
        }
        CBasePlayer* player = UTIL_GetLocalPlayer();
        if (player != nullptr && gpGlobals->curtime - m_flThrown > kPickupDelay &&
            (player->WorldSpaceCenter() - WorldSpaceCenter()).Length() < kPhysCatchRadius) {
            Return();
            return;
        }
        SetNextThink(gpGlobals->curtime + kPhysThink);
    }

    void CrowbarTouch(CBaseEntity* other) {
        CBasePlayer* thrower = ToBasePlayer(GetOwnerEntity());
        if (other == nullptr) {
            return;
        }
        if (other->IsPlayer()) {
            if (!m_bFlying || gpGlobals->curtime - m_flThrown > kPickupDelay) {
                Return();
            }
            return;
        }
        if (!m_bFlying) {
            return;
        }
        if (other->m_takedamage != DAMAGE_NO) {
            CTakeDamageInfo info(this, thrower ? static_cast<CBaseEntity*>(thrower) : this,
                                 kDamage, DMG_CLUB);
            CalculateMeleeDamageForce(&info, GetAbsVelocity(), GetAbsOrigin());
            other->TakeDamage(info);
            EmitSound("Weapon_Crowbar.Melee_Hit");
        } else if (!other->IsSolid() || other->IsSolidFlagSet(FSOLID_TRIGGER)) {
            return;
        }
        Stop();
    }

    void Stop() {
        m_bFlying = false;
        SetLocalAngularVelocity(vec3_angle);
        SetAbsVelocity(GetAbsVelocity() * 0.1f);
        SetGravity(1.0f);
        SetMoveType(MOVETYPE_FLYGRAVITY, MOVECOLLIDE_FLY_BOUNCE);
    }

    void ReturnThink() { Return(); }

    void Return() {
        SetTouch(nullptr);
        SetThink(nullptr);
        UTIL_Remove(this);
        CBasePlayer* player = UTIL_GetLocalPlayer();
        // The Crowbar is a starting item, so the gate always lets it back.
        if (player != nullptr && player->IsAlive() &&
            player->Weapon_OwnsThisType("weapon_crowbar") == nullptr) {
            ap::GrantWeapon(player, "weapon_crowbar");  // a return, not a find
        }
    }

private:
    float m_flThrown = 0.0f;
    bool m_bFlying = false;
    bool m_bPhysics = false;
};

LINK_ENTITY_TO_CLASS(ap_thrown_crowbar, CAPThrownCrowbar);

BEGIN_DATADESC(CAPThrownCrowbar)
    DEFINE_FIELD(m_flThrown, FIELD_TIME),
    DEFINE_FIELD(m_bFlying, FIELD_BOOLEAN),
    DEFINE_FIELD(m_bPhysics, FIELD_BOOLEAN),
    DEFINE_ENTITYFUNC(CrowbarTouch),
    DEFINE_THINKFUNC(ReturnThink),
    DEFINE_THINKFUNC(PhysicsThink),
END_DATADESC()

namespace ap {

bool CrowbarThrown() {
    return gEntList.FindEntityByClassname(nullptr, kThrownClass) != nullptr;
}

void MeleePrecache() { UTIL_PrecacheOther(kThrownClass); }

void CrowbarSecondary(CBaseCombatWeapon* crowbar) {
    CBasePlayer* player = crowbar ? ToBasePlayer(crowbar->GetOwner()) : nullptr;
    if (player == nullptr || !Gating()) {
        return;
    }
    if (!State().Has(kMeleeThrowItem)) {
        MeleeThrowRefused();
        return;
    }
    if (crowbar->m_flNextSecondaryAttack > gpGlobals->curtime) {
        return;
    }
    Vector forward;
    player->EyeVectors(&forward);
    auto* thrown = static_cast<CAPThrownCrowbar*>(CreateEntityByName(kThrownClass));
    if (thrown == nullptr) {
        return;
    }
    thrown->SetAbsOrigin(player->Weapon_ShootPosition() + forward * 16.0f);
    if (ap_crowbar_throw_style.GetInt() == 1) {
        // Murder: Angle(-28, 0, 0) + EyeAngles, then turned -90 about its right axis.
        QAngle ang = player->EyeAngles();
        ang.x += kPhysPitchUp;
        Vector right;
        AngleVectors(ang, nullptr, &right, nullptr);
        matrix3x4_t base, turn, out;
        AngleMatrix(ang, base);
        MatrixBuildRotationAboutAxis(right, -90.0f, turn);
        ConcatTransforms(turn, base, out);
        MatrixAngles(out, ang);
        thrown->SetAbsAngles(ang);
        thrown->UsePhysics();
    } else {
        thrown->SetAbsAngles(player->EyeAngles());
    }
    thrown->SetOwnerEntity(player);
    DispatchSpawn(thrown);
    IPhysicsObject* phys = thrown->UsingPhysics() ? thrown->VPhysicsGetObject() : nullptr;
    if (phys != nullptr) {
        Vector velocity = forward * (kPhysCharge * 1000.0f + 200.0f);
        AngularImpulse spin(0.0f, kPhysSpin, 0.0f);
        phys->AddVelocity(&velocity, &spin);
    } else {
        thrown->SetAbsVelocity(forward * kSpeed + Vector(0, 0, kLift));
    }
    crowbar->EmitSound("Weapon_Crowbar.Single");
    // The crowbar leaves the hand; the loadout holds off while it is out.
    if (player->GetActiveWeapon() == crowbar) {
        player->ClearActiveWeapon();
    }
    player->RemovePlayerItem(crowbar);
    UTIL_Remove(crowbar);
    player->SwitchToNextBestWeapon(nullptr);
}


}  // namespace ap

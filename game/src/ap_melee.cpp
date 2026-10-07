#include "cbase.h"
#include "player.h"
#include "basecombatweapon_shared.h"

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
        SetMoveType(MOVETYPE_FLYGRAVITY, MOVECOLLIDE_FLY_CUSTOM);
        SetSolid(SOLID_BBOX);
        AddSolidFlags(FSOLID_TRIGGER | FSOLID_NOT_STANDABLE);
        UTIL_SetSize(this, Vector(-4, -4, -4), Vector(4, 4, 4));
        SetGravity(kGravity);
        SetLocalAngularVelocity(QAngle(-900, 0, 0));
        SetTouch(&CAPThrownCrowbar::CrowbarTouch);
        SetThink(&CAPThrownCrowbar::ReturnThink);
        SetNextThink(gpGlobals->curtime + kReturnSeconds);
        m_flThrown = gpGlobals->curtime;
        m_bFlying = true;
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
};

LINK_ENTITY_TO_CLASS(ap_thrown_crowbar, CAPThrownCrowbar);

BEGIN_DATADESC(CAPThrownCrowbar)
    DEFINE_FIELD(m_flThrown, FIELD_TIME),
    DEFINE_FIELD(m_bFlying, FIELD_BOOLEAN),
    DEFINE_ENTITYFUNC(CrowbarTouch),
    DEFINE_THINKFUNC(ReturnThink),
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
    CBaseEntity* thrown = CreateEntityByName(kThrownClass);
    if (thrown == nullptr) {
        return;
    }
    thrown->SetAbsOrigin(player->Weapon_ShootPosition() + forward * 16.0f);
    thrown->SetAbsAngles(player->EyeAngles());
    thrown->SetOwnerEntity(player);
    DispatchSpawn(thrown);
    thrown->SetAbsVelocity(forward * kSpeed + Vector(0, 0, kLift));
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

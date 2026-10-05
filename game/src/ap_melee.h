// Melee Throw: once the item arrives, the crowbar's secondary fire throws it.
//
// HL1's tuning (`.claude/HL1_LEARNINGS.md` section 8): four times a swing's
// damage, fast and flat, lands where it stops and is picked up by walking
// over it, or comes back by itself after ten seconds.

#pragma once

class CBaseCombatWeapon;

namespace ap {

// hl2/weapon_crowbar.h SecondaryAttack.
void CrowbarSecondary(CBaseCombatWeapon* crowbar);

// A thrown crowbar is out: the loadout must not hand back another.
bool CrowbarThrown();

void MeleePrecache();

}  // namespace ap

// Gameplay: what is gated, what is reported, where the player may go.
//
// Every function here is what one line in a patched SDK file calls (see
// `game/sdk.patch` and `game/README.md`), or what `ap_main` calls from its
// game system. Decisions are made in the hook; anything that acts on the
// engine (a level change, a user message, a grant) is deferred to the frame.

#pragma once

#include <string>

class CBaseEntity;
class CBasePlayer;
class CBaseCombatWeapon;

namespace ap {

struct PendingEvent;

// --- from ap_main --------------------------------------------------------

void GameLevelStart();                  // LevelInitPostEntity
void GameFrame();                       // every frame, after the poll
void GameSnapshotChanged();             // a new snapshot was parsed
void GameEvent(const PendingEvent& event);  // ITEM, TRAP, DEATHLINK
bool GameDispatch(const std::string& name, const std::string& rest);
void GameHelp();
void GameStatus();

// Is the seed gating anything? Not before a client has named a slot: a
// player who never started a client plays retail Half-Life 2.
bool Gating();

// --- hooks in the SDK ----------------------------------------------------

// basecombatweapon_shared.cpp DefaultTouch, before BumpWeapon.
enum class Touch { kAllow, kRefuse, kConsume };
Touch WeaponTouch(CBasePlayer* player, CBaseCombatWeapon* weapon);

// player.cpp GiveNamedItem, first line. True refuses the give.
bool RefuseGive(CBasePlayer* player, const char* classname);

// hl2/item_suit.cpp MyTouch. Reports the suit check; the suit itself is
// ours to equip, so the item is always taken (its map outputs fire).
void SuitTouched(CBasePlayer* player);

// hl2/item_healthkit.cpp, hl2/func_recharge.cpp Use.
void ChargerUsed(CBaseEntity* charger, CBaseEntity* user);

// triggers.cpp ChangeLevelNow. True blocks the level change.
bool BlockChangeLevel(const char* next_map);

// player.cpp Event_Killed, CRevertSaved::InputReload.
void PlayerKilled();
void ReloadFired();

// EnvMessage.cpp CCredits::RollOutroCredits: the finale's end.
void OutroCredits();

// player.cpp CStripWeapons::StripWeapons.
void WeaponsStripped();

// player.cpp CanEnterVehicle. False refuses entry; never ejects.
bool CanEnterVehicle(CBasePlayer* player, CBaseEntity* vehicle);

// hl2/vehicle_airboat.cpp. Whether the mounted gun works, and a trigger
// pull on a gun that does not (for the refusal notice).
bool AirboatGunAllowed();
void AirboatGunPulled();

// hl2/weapon_physcannon.cpp. Stages held of Progressive Gravity Gun (4 when
// not gating): 1 holds and drops, 2 punts, 3 lets the Citadel supercharge it
// (organics refused), 4 is the full super gravity gun.
int GravityGunStage();
void GravityGunRefused(const char* what);

// hl2/hl2_player.cpp. Aux power (sprint) needs the HEV Suit item; the
// flashlight needs the Flashlight item.
bool SuitPowerAllowed();
bool FlashlightAllowed();

}  // namespace ap

// Gameplay: what is gated, what is reported, where the player may go.
//
// Every function here is what one line in a patched SDK file calls (see
// `game/sdk.patch` and `game/README.md`), or what `ap_main` calls from its
// game system. Decisions are made in the hook; anything that acts on the
// engine (a level change, a user message, a grant) is deferred to the frame.

#pragma once

#include <string>
#include <utility>
#include <vector>

class CBaseEntity;
class CBasePlayer;
class CBaseCombatWeapon;
class CTakeDamageInfo;

namespace ap {

struct PendingEvent;
struct Chapter;

// --- from ap_main --------------------------------------------------------

void GameLevelStart();                  // LevelInitPostEntity
void GameFrame();                       // every frame, after the poll
void GameSnapshotChanged();             // a new snapshot was parsed
void GameEvent(const PendingEvent& event);  // ITEM, TRAP, DEATHLINK
bool GameDispatch(const std::string& name, const std::string& rest);
void GameHelp();
void GameStatus();

// GiveNamedItem as our own grant: past the gate, and never a check.
CBaseEntity* GrantWeapon(CBasePlayer* player, const char* classname);

// Is the seed gating anything? Not before a client has named a slot: a
// player who never started a client plays retail Half-Life 2.
bool Gating();

// --- for ap_nav ----------------------------------------------------------

std::string ChapterStatusText(const Chapter& chapter);
// May a warp go to this chapter, and to this part of it (1-based)?
bool WarpOpen(const Chapter& chapter);
bool PartOpen(const Chapter& chapter, int part);
// The player's named warp points: label and map.
std::vector<std::pair<std::string, std::string>> WarpPoints();
bool HeldItem(const std::string& item);

// --- hooks in the SDK ----------------------------------------------------

// basecombatweapon_shared.cpp DefaultTouch, before BumpWeapon.
enum class Touch { kAllow, kRefuse, kConsume };
Touch WeaponTouch(CBasePlayer* player, CBaseCombatWeapon* weapon);

// DefaultTouch again, once, when a refused weapon was one the level scripted
// around (its pickup outputs just fired). Such weapons are spawned onto the
// player, so this swaps it for a copy on the floor in front of them.
void ScriptedWeaponRefused(CBasePlayer* player, CBaseCombatWeapon* weapon);

// basecombatcharacter.cpp and hl2/npc_combine.cpp Event_Killed. In the Citadel
// a dropped weapon dissolves only if this is true: the player's gravity gun
// did the killing (a punt, a thrown prop, an energy ball it caught; not one
// the Pulse Rifle fired).
bool GravityGunKill(const CTakeDamageInfo& info);
// basecombatcharacter.cpp, a dissolving kill. Whether the dropped weapon
// dissolves with the body: as retail outside the Citadel, only for a gravity
// gun kill inside it.
bool DissolveDroppedWeapon(const CTakeDamageInfo& info);

// player.cpp GiveNamedItem, first line. True refuses the give, and the weapon
// is left on the floor in front of the player instead.
bool RefuseGive(CBasePlayer* player, const char* classname);

// hl2/item_suit.cpp MyTouch. Reports the suit check; the suit itself is
// ours to equip, so the item is always taken (its map outputs fire).
void SuitTouched(CBasePlayer* player, CBaseEntity* suit);

// hl2/item_healthkit.cpp, hl2/func_recharge.cpp Use.
void ChargerUsed(CBaseEntity* charger, CBaseEntity* user);

// triggers.cpp ChangeLevelNow. True blocks the level change.
bool BlockChangeLevel(const char* next_map);

// player.cpp OnTakeDamage, on its copy of the damage: trap junk barely hurts
// and never kills (ap_traps.cpp).
void AdjustPlayerDamage(CBasePlayer* player, CTakeDamageInfo& info);

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
// hl2/vehicle_jeep.cpp. The same for the buggy's tau cannon.
bool BuggyGunAllowed();
void BuggyGunPulled();

// ap_melee.cpp. Crowbar alt-fire without the Melee Throw item: a notice when
// the seed has Melee Throw in its pool.
void MeleeThrowRefused();

// hl2/weapon_physcannon.cpp. Stages held of Progressive Gravity Gun (4 when
// not gating): 1 holds and drops, 2 punts, 3 lets the Citadel supercharge it
// (organics refused), 4 is the full super gravity gun.
int GravityGunStage();
void GravityGunRefused(const char* what);

// hl2/hl2_player.cpp. Aux power (sprint) needs the HEV Suit item; the
// flashlight needs the Flashlight item.
bool SuitPowerAllowed();
// SuitPower_Update and SuitPower_Charge: the meter's ceiling, a quarter per
// Progressive Aux Power held when the seed randomizes it (else 100).
float AuxPowerCap();
bool FlashlightAllowed();

}  // namespace ap

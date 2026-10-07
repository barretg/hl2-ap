// The traps. All nuisances rather than punishments: none should cost a run.
//
//   NPC Trap            four story characters, each wearing a random one of
//                       the story models and a random AI (citizen, Barney,
//                       the monk, Kleiner, Eli...), which follows the player,
//                       wanders, or runs away from them
//   Headcrab Trap       four headcrabs
//   Butterfingers Trap  the weapon in hand is flung away as a physics object;
//                       the suit hands it back after half a minute (option)
//   Manhack Swarm Trap  four manhacks (HL1's Bot Swarm: HL2 has no bots)
//   Rollermine Trap     three rollermines
//   Bunny Hop Trap      the player jumps whenever they land, for a while
//   Sticky Key Trap     one movement key is held down for a while, named
//   Reload Trap         the weapon in hand reloads from empty; the magazine
//                       goes back into the reserve first, so no ammo is lost
//   Crow Trap           a dozen crows around the player
//   Junk Trap           loose props fall on the player from above; they
//                       barely hurt (AdjustPlayerDamage)
//
// Every model a trap can spawn is precached at map load: spawning one that
// is not is fatal.

#pragma once

#include <string>

class CBaseEntity;
class CBasePlayer;

namespace ap {

// LevelInitPostEntity, before anything spawns a trap. Not PreEntity: see
// ap_main.cpp.
void TrapsPrecache();

// LevelInitPostEntity: forget the previous map's trap state, and let go of
// any key a trap was holding (the client's keys outlive the level).
void TrapsLevelStart();

// A TRAP delivery. Queued, and sprung once the player has been in the level
// for a while: arriving during a load means spawning into an unsettled map.
void QueueTrap(const std::string& name);

// Every frame, once the client is ready.
void TrapsFrame();

// Is this weapon out of the player's hands because Butterfingers took it?
// The loadout asks, or it would hand the weapon straight back.
bool Withheld(const std::string& classname);

// The pickup gate asks about every weapon touched. kNotTrap for any weapon
// but the one Butterfingers threw; for that one, whether it may be picked up
// yet (never a check: walking back onto it is not finding the map's).
enum class TrapDrop { kNotTrap, kTooSoon, kTaken };
TrapDrop TrapDropTouched(CBaseEntity* weapon);

// How long a trap waits after arriving, in game seconds.
constexpr float kTrapDelaySeconds = 5.0f;
// How long a Butterfingers victim goes without their weapon.
constexpr float kButterfingersReturnSeconds = 30.0f;
// How long Bunny Hop and Sticky Key last.
constexpr float kHeldKeySeconds = 15.0f;

}  // namespace ap

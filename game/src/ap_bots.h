// The Bot Swarm Trap's bots: `ap_bot`, HL1's fun-with-bots brain (see the HL1
// port's ap_bots.cpp) on an NPC body. It runs and jumps about with no node
// graph, swings a crowbar at whatever it bumps into (the player included),
// then turns tail for a moment. Map NPCs neither see nor mind it.
//
// Each wears a random human, Combine, vortigaunt or zombie model, picked from
// every one actually on disk: a model the install lacks is never precached or
// set, and none is precached into a nearly full model table.

#pragma once

#include "mathlib/vector.h"

class CBaseEntity;

namespace ap {

constexpr int kBotSwarmCount = 6;
constexpr int kBotHealth = 30;
constexpr float kBotCrowbarDamage = 5.0f;

// At map load: which models exist (each is precached when first worn), the
// crowbar, sounds.
void BotsPrecache();

// Whether any bot model is usable on this map, and how many are.
bool BotsAvailable();
int BotModelCount();

// Starts the bag of models over, so the next BotModelCount() bots wear every
// usable model once.
void RefillBotModels();

// A bot standing at `feet`, facing `yaw`; null if none could be made.
CBaseEntity* SpawnBot(const Vector& feet, float yaw);

}  // namespace ap

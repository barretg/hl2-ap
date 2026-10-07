// Default key binds for the Archipelago commands, set once per game launch.
//
// Only where the player has not already chosen: a key bound to anything is
// left alone, and a command bound to any key is not bound again. So a player
// who moves the menu to another key keeps it there.

#include "cbase.h"
#include "igamesystem.h"
#include "inputsystem/ButtonCode.h"

#include "tier0/memdbgon.h"

namespace {

struct DefaultBind {
    ButtonCode_t key;
    const char* key_name;  // as `bind` spells it
    const char* command;
};

const DefaultBind kBinds[] = {
    {KEY_MINUS, "-", "ap menu"},
};

class CBindsSystem : public CAutoGameSystem {
public:
    CBindsSystem() : CAutoGameSystem("CArchipelagoBinds") {}

    void LevelInitPostEntity() override {
        if (done_) {
            return;
        }
        done_ = true;
        for (const DefaultBind& bind : kBinds) {
            const char* current = engine->Key_BindingForKey(bind.key);
            if (engine->Key_LookupBinding(bind.command) != nullptr ||
                (current != nullptr && *current != '\0')) {
                continue;
            }
            char line[128];
            Q_snprintf(line, sizeof(line), "bind \"%s\" \"%s\"\n", bind.key_name, bind.command);
            engine->ClientCmd_Unrestricted(line);
        }
    }

private:
    bool done_ = false;
};

CBindsSystem g_binds;

}  // namespace

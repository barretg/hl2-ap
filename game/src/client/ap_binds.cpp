// Key binds for the Archipelago commands, set once per game launch.
//
// The menu's bind is a default: set only where the player has not already
// chosen, so a player who moves the menu to another key keeps it there.
//
// 0 is forced to slot10, because the numbered menu's exit is item 10 and
// only reaches the menu through slot10; the anniversary update binds 0 to
// vr_toggle. That moves to backslash when backslash is free.

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

const DefaultBind kDefaults[] = {
    {KEY_MINUS, "-", "ap menu"},
};

void Bind(const char* key_name, const char* command) {
    char line[128];
    Q_snprintf(line, sizeof(line), "bind \"%s\" \"%s\"\n", key_name, command);
    engine->ClientCmd_Unrestricted(line);
}

bool Unbound(ButtonCode_t key) {
    const char* current = engine->Key_BindingForKey(key);
    return current == nullptr || *current == '\0';
}

class CBindsSystem : public CAutoGameSystem {
public:
    CBindsSystem() : CAutoGameSystem("CArchipelagoBinds") {}

    void LevelInitPostEntity() override {
        if (done_) {
            return;
        }
        done_ = true;
        for (const DefaultBind& bind : kDefaults) {
            if (engine->Key_LookupBinding(bind.command) == nullptr && Unbound(bind.key)) {
                Bind(bind.key_name, bind.command);
            }
        }
        const char* zero = engine->Key_BindingForKey(KEY_0);
        if (zero == nullptr || Q_stricmp(zero, "slot10") != 0) {
            if (zero != nullptr && Q_stricmp(zero, "vr_toggle") == 0 && Unbound(KEY_BACKSLASH)) {
                Bind("\\", "vr_toggle");
            }
            Bind("0", "slot10");
        }
    }

private:
    bool done_ = false;
};

CBindsSystem g_binds;

}  // namespace

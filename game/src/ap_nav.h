// Navigation: the `!menu` menu, `!find`, `!trace`, and the tracker's menu view.
//
// The menu is the engine's own numbered HUD menu (the `ShowMenu` user
// message): 1 to 7 pick, 8 goes back, 9 shows more, 0 closes. The client
// sends `menuselect <n>` for a key pressed while it is open; the action runs
// on the next frame, never inside the command.

#pragma once

#include <string>

namespace ap {

// LevelInitPreEntity: the beam sprite `!trace` draws with.
void NavPrecache();
// LevelInitPostEntity: the menu closes and a trace stops with the old map.
void NavLevelStart();
// Every frame once the client is ready: menu picks, the trace's beams.
void NavFrame();

// `!menu`, `!find`, `!trace`. False for any other command.
bool NavDispatch(const std::string& name, const std::string& rest);
// `!tracker [text]`: its menu view, beside the console listing.
void NavTracker(const std::string& filter);
// The `menuselect` command: a menu key, 1 to 9, or 10 for 0.
void NavMenuSelect(int key);

}  // namespace ap

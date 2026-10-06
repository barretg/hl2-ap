// Freeze watchdog, test builds only (`HL2AP_TEST_BUILD`).
//
// A background thread watches two frame counters: the server's (beaten from
// our per-frame system) and the client's (`HL2AP_ClientFrames`, exported by
// our client dll). When both stop for `kStallSeconds`, the game is frozen
// rather than paused or loading, and the thread writes
// `archipelago/watchdog.txt`: the stage our code last entered, the main
// thread's instruction pointer and a scan of its stack for return addresses
// (as module+offset), and `watchdog.dmp`, a minidump of the process. If the
// game later resumes, that is appended too, so a long load reads as one.
//
// Kept free of SDK headers so it can include windows.h. Release builds get
// empty inlines.

#pragma once

#ifdef HL2AP_TEST_BUILD

// Main thread, once the store dir is known. Later calls only update the dir.
void WatchdogStart(const char* store_dir);
// Once per server frame.
void WatchdogBeat();
// What our code is doing now. Must be a string literal (stored by pointer).
void WatchdogStage(const char* stage);

#else

inline void WatchdogStart(const char*) {}
inline void WatchdogBeat() {}
inline void WatchdogStage(const char*) {}

#endif

// In-game half of the scenario harness, `tests/aptest/aptest.py`.
//
// The Python script stands in for the client: it writes the snapshot, watches
// what the game sends and records verdicts. It runs in a terminal; the player
// drives it from here, in chat (`!pass`) or the console (`ap_test pass`):
//
//   !pass [note]  !fail <note>  !note <text>   record a verdict, next scenario
//   !next  !prev  !redo  !go <n>               move between scenarios
//   !info  !status  !list [text]               what the harness knows
//   !groups  !group <name>                     list or switch scenario groups
//   !give <item>  !take <item>                 change what the snapshot holds
//   !tp                                        back to the scenario's spot
//
// Every verb but `tp` goes to the harness as an `APTEST` line in `ap_out.txt`.
// The harness answers in `aptest_say.txt`, shown here, and starts a scenario
// by rewriting `aptest_go.txt`, which loads its map, puts the player at its
// spot and runs its setup commands.
//
// Test builds only (`HL2AP_TEST_BUILD`): a release dll registers no `ap_test`
// command and `TestDispatch` declines everything. The harness tells the two
// builds apart by that command's name in the binary.

#pragma once

#include <string>

namespace ap {

// Whether this dll was built with the harness in.
bool TestBuild();

// A harness verb typed in chat or `ap`. False if it is not one, or in a
// release build. Asked before `ap_main`'s own commands, so in a test build
// `!status` is the harness's.
bool TestDispatch(const std::string& name, const std::string& rest);

// Every frame: shows what the harness said, loads a scenario it started, and
// places the player once they have spawned.
void RunTestHarness();

}  // namespace ap

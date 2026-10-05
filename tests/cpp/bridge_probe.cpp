// Host-side driver for the game's engine-free modules (ap_text, ap_state,
// ap_bridge), built natively by tests/test_bridge_cpp.py so the game half of
// the protocol is checked against the Python half without the game.
//
//   bridge_probe <store> poll [poll ...]   parse ap_in.txt, print what was read
//   bridge_probe <store> send <kind> <arg>...
//   bridge_probe <store> ack <seq>

#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

#include "ap_bridge.h"
#include "ap_state.h"

namespace {

template <typename Set>
void PrintSet(const char* key, const Set& values) {
    std::printf("%s=", key);
    bool first = true;
    for (const auto& value : values) {
        std::printf(first ? "%s" : ";%s", std::to_string(value).c_str());
        first = false;
    }
    std::printf("\n");
}

void PrintStrings(const char* key, const std::set<std::string>& values) {
    std::printf("%s=", key);
    bool first = true;
    for (const std::string& value : values) {
        std::printf(first ? "%s" : ";%s", value.c_str());
        first = false;
    }
    std::printf("\n");
}

}  // namespace

int main(int argc, char** argv) {
    if (argc < 3) {
        return 2;
    }
    ap::Bridge bridge;
    bridge.Open(argv[1]);
    const std::string mode = argv[2];
    if (mode == "send") {
        std::vector<std::string> args(argv + 4, argv + argc);
        bridge.Send(argv[3], args);
        return 0;
    }
    if (mode == "ack") {
        bridge.Acknowledge(std::atoi(argv[3]));
        return 0;
    }
    // One `poll` per argument from index 2, in one process, so a test can see
    // that an unchanged file is not reparsed.
    for (int i = 2; i < argc; ++i) {
        ap::Snapshot state;
        std::vector<ap::PendingEvent> events;
        const bool read = bridge.Poll(state, events);
        std::printf("poll=%d\n", read ? 1 : 0);
        if (!read) {
            continue;
        }
        std::printf("session=%s\nslot=%s\ndata_version=%s\nconnected=%d\n",
                    state.session.c_str(), state.slot.c_str(),
                    state.data_version.c_str(), state.connected ? 1 : 0);
        PrintStrings("chapters", state.open_chapters);
        PrintStrings("excluded", state.excluded_chapters);
        PrintStrings("items", state.held_items);
        PrintStrings("ungated", state.ungated_classnames);
        std::printf("starting=");
        for (size_t j = 0; j < state.starting_weapons.size(); ++j) {
            std::printf(j ? ";%s" : "%s", state.starting_weapons[j].c_str());
        }
        std::printf("\n");
        std::printf("counts=");
        bool first_count = true;
        for (const auto& entry : state.counts) {
            std::printf(first_count ? "%s:%d" : ";%s:%d", entry.first.c_str(), entry.second);
            first_count = false;
        }
        std::printf("\n");
        PrintSet("checked", state.checked);
        PrintSet("missing", state.missing);
        for (const auto& option : state.options) {
            std::printf("option.%s=%s\n", option.first.c_str(), option.second.c_str());
        }
        std::printf("now=%ld\n", bridge.Now());
        for (const ap::PendingEvent& event : events) {
            std::printf("event=%d|%s|%s|%ld\n", event.seq, event.kind.c_str(),
                        event.payload.c_str(), event.stamp);
        }
    }
    return 0;
}

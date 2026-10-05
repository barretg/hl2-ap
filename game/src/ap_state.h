// What the client last told us, and nothing else.
//
// The game side is stateless across map loads and saves on purpose: everything
// here is rebuilt from the next snapshot, so a quickload cannot desync and a
// re-sent check is a no-op on the server.
//
// Engine-free, like `ap_text` and `ap_bridge`.

#pragma once

#include <map>
#include <set>
#include <string>
#include <vector>

namespace ap {

struct Snapshot {
    bool connected = false;
    std::string session;        // changes when the client restarts
    std::string data_version;   // ours must match, or ids mean different things

    // Which slot of which seed is being played, "<seed>:<slot>". This is what
    // says the run has changed underneath us, and it is a different question
    // from the session above: a client restarted onto the same slot is a blip
    // and must move nobody, while a different slot connected from the client
    // already running changes everything the run is about.
    //
    // Empty while the client is disconnected, which is no news rather than a
    // new slot, so the last one named stands.
    std::string slot;

    std::set<std::string> open_chapters;      // missions that may be entered
    std::set<std::string> excluded_chapters;  // not in this seed at all
    std::set<std::string> held_items;         // item names the player has been sent
    std::set<std::string> ungated_classnames; // left entirely to the game
    std::vector<std::string> starting_weapons;
    // Copies held of items that come in copies (`counts=`).
    std::map<std::string, int> counts;

    std::set<long> checked;   // for the tracker
    std::set<long> missing;   // ids in neither set are not in this seed

    // Every other `key=value` line: the seed's options. Kept as text so a new
    // option needs no protocol or parser change; the code that acts on one asks
    // for it by name, with the fallback that reproduces a client older than the
    // option.
    std::map<std::string, std::string> options;

    bool Has(const std::string& item) const {
        return held_items.find(item) != held_items.end();
    }
    // Copies of an item: its count when it comes in copies, else 1 or 0.
    int Count(const std::string& item) const {
        const auto it = counts.find(item);
        if (it != counts.end()) {
            return it->second;
        }
        return Has(item) ? 1 : 0;
    }
    bool ChapterOpen(const std::string& key) const {
        return open_chapters.find(key) != open_chapters.end();
    }
    bool ChapterExcluded(const std::string& key) const {
        return excluded_chapters.find(key) != excluded_chapters.end();
    }
    bool Ungated(const std::string& classname) const {
        return ungated_classnames.find(classname) != ungated_classnames.end();
    }
    // A location the seed does not contain at all. Before the first snapshot
    // both sets are empty, which is not the same answer, so that reads as "in
    // the seed" rather than as "nothing is".
    bool InSeed(long id) const {
        if (checked.empty() && missing.empty()) {
            return true;
        }
        return checked.find(id) != checked.end() || missing.find(id) != missing.end();
    }

    // An option's raw text, or empty when the client did not send it.
    std::string Option(const std::string& key) const;
    // "1" is true, anything else false; `fallback` when absent.
    bool OptionBool(const std::string& key, bool fallback) const;
    long OptionLong(const std::string& key, long fallback) const;
};

// The live one. Replaced wholesale by each poll rather than merged: a partial
// update is how the two halves come to disagree.
Snapshot& State();

}  // namespace ap

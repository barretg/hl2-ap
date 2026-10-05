// The installed `checkdata.txt`: chapters, locations and what gates what.
//
// Generated from the same `campaign.json` the apworld reads
// (`tools/gen_checkdata.py`, whose header documents every record), so a
// location id means the same thing on both sides. Engine-free, like `ap_text`
// and `ap_bridge`, and tested on the host by `tests/test_checkdata_cpp.py`.

#pragma once

#include <map>
#include <set>
#include <string>
#include <utility>
#include <vector>

namespace ap {

struct Chapter {
    int index = 0;
    std::string key;         // its first map; permanent
    std::string number;      // the chapter cfg suffix: "9a"
    std::string name;
    std::vector<std::string> maps;
    bool is_goal = false;
    std::string campaign;
    std::string complete_on; // forward_exit or finale
    std::vector<std::pair<std::string, std::string>> exits;  // changelevels out
};

struct Location {
    long id = 0;
    std::string map;
    std::string type;        // map_reached, chapter_complete, charger, ...
    std::string arg;
    std::string name;
    bool has_position = false;
    float position[3] = {0, 0, 0};
};

struct Source {
    long location = 0;
    std::string map;
    bool has_position = false;
    float position[3] = {0, 0, 0};
    std::string how;
    std::string spawner;
    bool confirmed = false;
};

struct VehicleKey {
    std::string vehiclescript;
    std::string item;
};

class CheckData {
public:
    // False when the file is missing or is not a format this build reads; the
    // previous contents are kept either way only if the new file parsed.
    bool Load(const std::string& path);
    bool Loaded() const { return format_ != 0; }

    int Format() const { return format_; }
    const std::string& DataVersion() const { return data_version_; }
    const std::string& Hub() const { return hub_; }

    const std::vector<Chapter>& Chapters() const { return chapters_; }
    const std::vector<Location>& Locations() const { return locations_; }
    const std::vector<Source>& Sources() const { return sources_; }

    // The chapter a map belongs to, or null (the hub, menu backgrounds).
    const Chapter* ChapterOfMap(const std::string& map) const;
    const Chapter* ChapterByKey(const std::string& key) const;
    // A chapter typed by a player: its number ("9a"), index+1, key or name,
    // case and punctuation ignored.
    const Chapter* FindChapter(const std::string& text) const;

    // Location ids, 0 when there is none.
    long MapReached(const std::string& map) const;
    long ChapterComplete(const std::string& chapter_key) const;
    // weapon_pickup, item_pickup or weapon_upgrade of this classname.
    long Pickup(const std::string& type, const std::string& classname) const;
    // Charger checks on a map.
    std::vector<const Location*> Chargers(const std::string& map) const;
    const Location* LocationById(long id) const;

    // The item a classname is refused without, or empty when ungated.
    std::string GateOf(const std::string& classname) const;
    // Every gated classname and its item.
    const std::map<std::string, std::string>& Gates() const { return gates_; }
    // Stages of a progressive item, 0 when it is not one.
    int Stages(const std::string& item) const;
    // The key a chapter's vehicle needs, or null.
    const VehicleKey* KeyFor(const std::string& chapter_key) const;
    // Maps that enable a vehicle upgrade (the Airboat Gun).
    const std::vector<std::string>* UpgradeMaps(const std::string& item) const;
    // Whether an entity of this targetname on this map is a cold-load kit
    // pickup (spawned only when the map is loaded directly). A template copy's
    // `&NNNN` suffix is ignored.
    bool IsKit(const std::string& map, const std::string& targetname) const;

private:
    int format_ = 0;
    std::string data_version_;
    std::string hub_;
    std::vector<Chapter> chapters_;
    std::vector<Location> locations_;
    std::vector<Source> sources_;
    std::map<std::string, std::string> gates_;
    std::map<std::string, int> stages_;
    std::map<std::string, VehicleKey> keys_;
    std::map<std::string, std::vector<std::string>> upgrades_;
    std::map<std::string, std::set<std::string>> kits_;
    std::map<std::string, size_t> chapter_of_map_;
};

// The formats this build reads.
constexpr int kCheckDataFormat = 1;

// The live one, loaded from the store on every map load.
CheckData& Data();

}  // namespace ap

#include "ap_checkdata.h"

#include <fstream>

#include "ap_text.h"

namespace ap {
namespace {

std::vector<std::string> List(const std::string& text, char delimiter) {
    std::vector<std::string> out;
    if (Trim(text).empty()) {
        return out;
    }
    for (const std::string& part : Split(text, delimiter)) {
        if (!Trim(part).empty()) {
            out.push_back(Trim(part));
        }
    }
    return out;
}

}  // namespace

bool CheckData::Load(const std::string& path) {
    std::ifstream file(path.c_str());
    if (!file) {
        return false;
    }
    CheckData parsed;
    std::string line;
    while (std::getline(file, line)) {
        line = Trim(line);
        if (line.empty() || line[0] == '#') {
            continue;
        }
        const std::vector<std::string> f = Split(line, '|');
        const std::string& kind = f[0];
        if (kind == "V" && f.size() >= 2) {
            parsed.format_ = static_cast<int>(ParseLong(f[1]));
            if (parsed.format_ != kCheckDataFormat) {
                return false;
            }
        } else if (kind == "D" && f.size() >= 2) {
            parsed.data_version_ = f[1];
        } else if (kind == "B" && f.size() >= 2) {
            parsed.hub_ = f[1];
        } else if (kind == "C" && f.size() >= 10) {
            Chapter chapter;
            chapter.index = static_cast<int>(ParseLong(f[1]));
            chapter.key = f[2];
            chapter.number = f[3];
            chapter.name = f[4];
            chapter.maps = List(f[5], ',');
            chapter.is_goal = ParseBool(f[6]);
            chapter.campaign = f[7];
            chapter.complete_on = f[8];
            for (const std::string& exit : List(f[9], ',')) {
                const size_t arrow = exit.find('>');
                if (arrow != std::string::npos) {
                    chapter.exits.emplace_back(exit.substr(0, arrow), exit.substr(arrow + 1));
                }
            }
            for (const std::string& map : chapter.maps) {
                parsed.chapter_of_map_[map] = parsed.chapters_.size();
            }
            parsed.chapters_.push_back(chapter);
        } else if (kind == "L" && f.size() >= 6) {
            Location location;
            location.id = ParseLong(f[1]);
            location.map = f[2];
            location.type = f[3];
            location.arg = f[4];
            location.name = f[5];
            if (f.size() >= 7) {
                location.has_position = ParseVector(f[6], location.position);
            }
            parsed.locations_.push_back(location);
        } else if (kind == "F" && f.size() >= 7) {
            Source source;
            source.location = ParseLong(f[1]);
            source.map = f[2];
            source.has_position = ParseVector(f[3], source.position);
            source.how = f[4];
            source.spawner = f[5];
            source.confirmed = ParseBool(f[6]);
            parsed.sources_.push_back(source);
        } else if (kind == "K" && f.size() >= 3) {
            parsed.gates_[f[1]] = f[2];
        } else if (kind == "P" && f.size() >= 3) {
            parsed.stages_[f[1]] = static_cast<int>(ParseLong(f[2]));
        } else if (kind == "H" && f.size() >= 4) {
            parsed.keys_[f[1]] = VehicleKey{f[2], f[3]};
        } else if (kind == "U" && f.size() >= 3) {
            parsed.upgrades_[f[1]] = List(f[2], ',');
        } else if (kind == "X" && f.size() >= 3) {
            for (const std::string& name : List(f[2], ',')) {
                parsed.kits_[Lower(f[1])].insert(Lower(name));
            }
        }
        // Unknown record kinds are a newer generator's; skipped, never fatal.
    }
    if (parsed.format_ == 0) {
        return false;
    }
    *this = parsed;
    return true;
}

const Chapter* CheckData::ChapterOfMap(const std::string& map) const {
    const auto it = chapter_of_map_.find(Lower(map));
    return it == chapter_of_map_.end() ? nullptr : &chapters_[it->second];
}

const Chapter* CheckData::ChapterByKey(const std::string& key) const {
    for (const Chapter& chapter : chapters_) {
        if (chapter.key == key) {
            return &chapter;
        }
    }
    return nullptr;
}

std::vector<const Chapter*> CheckData::MatchChapters(const std::string& text) const {
    const std::string want = Simplify(text);
    std::vector<const Chapter*> found;
    if (want.empty()) {
        return found;
    }
    auto tier = [&](auto matches) {
        for (const Chapter& chapter : chapters_) {
            if (matches(chapter)) {
                found.push_back(&chapter);
            }
        }
        return !found.empty();
    };
    auto word_starts = [&](const Chapter& chapter) {
        for (const std::string& word : Split(chapter.name, ' ')) {
            const std::string simple = Simplify(word);
            if (!simple.empty() && StartsWith(simple, want)) {
                return true;
            }
        }
        return false;
    };
    // A map name finds its own chapter, whatever the other tiers would say.
    if (const Chapter* by_map = ChapterOfMap(Lower(Trim(text)))) {
        found.push_back(by_map);
        return found;
    }
    tier([&](const Chapter& c) {
        return Simplify(c.number) == want || Simplify(c.key) == want ||
               Simplify(c.name) == want;
    }) ||
        tier([&](const Chapter& c) { return StartsWith(Simplify(c.name), want); }) ||
        tier(word_starts) ||
        tier([&](const Chapter& c) { return Simplify(c.name).find(want) != std::string::npos; });
    return found;
}

const Chapter* CheckData::FindChapter(const std::string& text) const {
    const std::vector<const Chapter*> found = MatchChapters(text);
    return found.size() == 1 ? found.front() : nullptr;
}

long CheckData::MapReached(const std::string& map) const {
    for (const Location& location : locations_) {
        if (location.type == "map_reached" && location.map == map) {
            return location.id;
        }
    }
    return 0;
}

long CheckData::ChapterComplete(const std::string& chapter_key) const {
    for (const Location& location : locations_) {
        if (location.type == "chapter_complete" && location.arg == chapter_key) {
            return location.id;
        }
    }
    return 0;
}

long CheckData::Pickup(const std::string& type, const std::string& classname) const {
    for (const Location& location : locations_) {
        if (location.type != type) {
            continue;
        }
        for (const std::string& name : List(location.arg, ',')) {
            if (name == classname) {
                return location.id;
            }
        }
    }
    return 0;
}

std::vector<const Location*> CheckData::Chargers(const std::string& map) const {
    std::vector<const Location*> out;
    for (const Location& location : locations_) {
        if (location.type == "charger" && location.map == map) {
            out.push_back(&location);
        }
    }
    return out;
}

const Location* CheckData::LocationById(long id) const {
    for (const Location& location : locations_) {
        if (location.id == id) {
            return &location;
        }
    }
    return nullptr;
}

std::string CheckData::GateOf(const std::string& classname) const {
    const auto it = gates_.find(classname);
    return it == gates_.end() ? std::string() : it->second;
}

int CheckData::Stages(const std::string& item) const {
    const auto it = stages_.find(item);
    return it == stages_.end() ? 0 : it->second;
}

const VehicleKey* CheckData::KeyFor(const std::string& chapter_key) const {
    const auto it = keys_.find(chapter_key);
    return it == keys_.end() ? nullptr : &it->second;
}

const std::vector<std::string>* CheckData::UpgradeMaps(const std::string& item) const {
    const auto it = upgrades_.find(item);
    return it == upgrades_.end() ? nullptr : &it->second;
}

bool CheckData::IsKit(const std::string& map, const std::string& targetname) const {
    const auto it = kits_.find(Lower(map));
    if (it == kits_.end() || targetname.empty()) {
        return false;
    }
    return it->second.count(Lower(targetname.substr(0, targetname.find('&')))) != 0;
}

CheckData& Data() {
    static CheckData data;
    return data;
}

}  // namespace ap

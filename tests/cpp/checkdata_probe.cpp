// Host-side driver for ap_checkdata, built by tests/test_checkdata_cpp.py.
//
//   checkdata_probe <file> <query> [args]   one answer per line

#include <cstdio>
#include <string>

#include "ap_checkdata.h"

int main(int argc, char** argv) {
    if (argc < 3) {
        return 2;
    }
    ap::CheckData data;
    if (!data.Load(argv[1])) {
        std::printf("load=0\n");
        return 0;
    }
    const std::string query = argv[2];
    const std::string a = argc > 3 ? argv[3] : "";
    const std::string b = argc > 4 ? argv[4] : "";
    if (query == "summary") {
        std::printf("format=%d\ndata_version=%s\nhub=%s\nchapters=%zu\nlocations=%zu\nsources=%zu\n",
                    data.Format(), data.DataVersion().c_str(), data.Hub().c_str(),
                    data.Chapters().size(), data.Locations().size(), data.Sources().size());
    } else if (query == "chapter_of") {
        const ap::Chapter* c = data.ChapterOfMap(a);
        std::printf("%s\n", c ? c->key.c_str() : "");
    } else if (query == "find") {
        const ap::Chapter* c = data.FindChapter(a);
        std::printf("%s\n", c ? c->key.c_str() : "");
    } else if (query == "exits") {
        const ap::Chapter* c = data.ChapterByKey(a);
        for (const auto& e : c->exits) {
            std::printf("%s>%s\n", e.first.c_str(), e.second.c_str());
        }
    } else if (query == "reached") {
        std::printf("%ld\n", data.MapReached(a));
    } else if (query == "complete") {
        std::printf("%ld\n", data.ChapterComplete(a));
    } else if (query == "pickup") {
        std::printf("%ld\n", data.Pickup(a, b));
    } else if (query == "chargers") {
        for (const ap::Location* l : data.Chargers(a)) {
            std::printf("%ld %s %.0f %.0f %.0f\n", l->id, l->arg.c_str(), l->position[0],
                        l->position[1], l->position[2]);
        }
    } else if (query == "gate") {
        std::printf("%s\n", data.GateOf(a).c_str());
    } else if (query == "stages") {
        std::printf("%d\n", data.Stages(a));
    } else if (query == "key") {
        const ap::VehicleKey* k = data.KeyFor(a);
        std::printf("%s\n", k ? (k->vehiclescript + "|" + k->item).c_str() : "");
    } else if (query == "kit") {
        std::printf("%d\n", data.IsKit(a, b) ? 1 : 0);
    } else if (query == "upgrade") {
        const auto* maps = data.UpgradeMaps(a);
        for (size_t i = 0; maps && i < maps->size(); ++i) {
            std::printf("%s\n", (*maps)[i].c_str());
        }
    }
    return 0;
}

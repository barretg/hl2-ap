#include "ap_state.h"

#include "ap_text.h"

namespace ap {

Snapshot& State() {
    static Snapshot state;
    return state;
}

std::string Snapshot::Option(const std::string& key) const {
    const auto found = options.find(key);
    return found == options.end() ? std::string() : found->second;
}

bool Snapshot::OptionBool(const std::string& key, bool fallback) const {
    const auto found = options.find(key);
    return found == options.end() ? fallback : ParseBool(found->second);
}

long Snapshot::OptionLong(const std::string& key, long fallback) const {
    const auto found = options.find(key);
    return found == options.end() ? fallback : ParseLong(found->second, fallback);
}

}  // namespace ap

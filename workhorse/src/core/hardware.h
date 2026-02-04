#pragma once

#include <unordered_set>

class Hardware {
public:
    enum class Type {
        CPU = 0,
        GPU,
        MAX_COUNT
    };

    Hardware(Type type);
    bool operator==(const Hardware& other) const;
    
    int getType() const;
    
private:
    Type _type;
};

namespace std {
    template <>
    struct hash<Hardware> {
        std::size_t operator()(const Hardware& other) const noexcept {
            return std::hash<int>{}(other.getType());
        }
    };
}
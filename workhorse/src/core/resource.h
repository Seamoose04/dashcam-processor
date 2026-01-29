#pragma once

#include <unordered_set>

class Resource {
public:
    enum Type {
        CPU,
        GPU,
    };

    Resource(Type type);
    bool operator==(const Resource& other) const;
    int getType() const;
    
private:
    Type _type;
};

namespace std {
    template <>
    struct hash<Resource> {
        std::size_t operator()(const Resource& other) const noexcept {
            return std::hash<int>{}(other.getType());
        }
    };
}
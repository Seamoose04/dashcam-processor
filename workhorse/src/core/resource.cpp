#include "resource.h"

Resource::Resource(Type type) {
    _type = type;
}

bool Resource::operator==(const Resource& other) const {
    return getType() == other.getType();
}

int Resource::getType() const {
    return static_cast<int>(_type);
}
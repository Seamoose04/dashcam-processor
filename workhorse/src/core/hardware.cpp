#include "hardware.h"

Hardware::Hardware(Type type) {
    _type = type;
}

bool Hardware::operator==(const Hardware& other) const {
    return getType() == other.getType();
}

int Hardware::getType() const {
    return static_cast<int>(_type);
}
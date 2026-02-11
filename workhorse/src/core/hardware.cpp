#include "hardware.h"

#include "core/task.h"

bool Hardware::operator==(const Hardware& other) const {
    return GetTypeName() == other.GetTypeName();
}

std::string Hardware::GetTypeName() const {
    return _type_name;
}

void Hardware::SetTypeName(std::string name) {
    _type_name = name;
}
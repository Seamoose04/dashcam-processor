#include "hardware.h"

#include "core/task.h"

Hardware::Hardware(Resources required_resources) {
    _required_resources = required_resources;
}

bool Hardware::operator==(const Hardware& other) const {
    return GetTypeName() == other.GetTypeName();
}

std::string Hardware::GetTypeName() const {
    return _type_name;
}

void Hardware::SetTypeName(std::string name) {
    _type_name = name;
}

Resources Hardware::GetRequiredResources() {
    return _required_resources;
}
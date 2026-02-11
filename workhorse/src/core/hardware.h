#pragma once

#include <unordered_set>
#include <string>
#include <memory>

#include "util/registry.h"
#include "core/taskQueue.h"
#include "core/logger.h"

class Task;

class Hardware {
public:
    Hardware() = default;
    virtual ~Hardware() = default;

    bool operator==(const Hardware& other) const;
    std::string GetTypeName() const;
    void SetTypeName(std::string name);

    virtual void Load(Logger* logger) const {};
    virtual void Process(std::shared_ptr<Task> task, Logger* logger, std::shared_ptr<TaskQueue> queue) const = 0;
    virtual void Unload(Logger* logger) const {};
    
protected:
    std::string _type_name;
};

namespace std {
    template <>
    struct hash<Hardware> {
        std::size_t operator()(const Hardware& other) const noexcept {
            return std::hash<std::string>{}(other.GetTypeName());
        }
    };
}

#define REGISTER_HARDWARE(DerivedType) REGISTER_TYPE(Hardware, DerivedType)
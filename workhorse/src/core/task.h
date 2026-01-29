#pragma once

#include <unordered_set>
#include <functional>

#include "core/resource.h"

class Task {
public:
    Task() = default;
    virtual void Prepare() = 0;
    virtual void Run() = 0;
    virtual void Finish() = 0;
    virtual void Stop(bool immediate=false) = 0;
    
protected:
    std::unordered_set<Resource> _resources_required;
};
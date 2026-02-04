#pragma once

#include <unordered_set>
#include <functional>

#include "core/hardware.h"
#include "util/flag.h"

class Task {
public:
    enum class Flags : unsigned int {
        Quit
    };

    Task() = default;
    bool operator==(const Task& other) const;

    void Start();
    virtual void Run() = 0;
    void Finish();
    void Stop();

protected:
    virtual void _Start() = 0;
    virtual void _Finish() = 0;

    std::unordered_set<Hardware> _hardware_required;
    Flag<Flags> _flags;
};
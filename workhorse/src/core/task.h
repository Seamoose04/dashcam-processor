#pragma once

#include <unordered_set>
#include <functional>

#include "core/hardware.h"
#include "core/logger.h"
#include "util/flag.h"

class Task {
public:
    enum class Flags : unsigned int {
        Quit
    };

    Task(Hardware type);
    bool operator==(const Task& other) const;

    void Start(Logger& logger);
    virtual void Run(Logger& logger) = 0;
    void Finish(Logger& logger);
    void Quit();

protected:
    virtual void _Start(Logger& logger) = 0;
    virtual void _Finish(Logger& logger) = 0;

    Hardware _type;
    Flag<Flags> _flags;
};
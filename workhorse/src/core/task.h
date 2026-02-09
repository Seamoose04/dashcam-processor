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

    void Run(Logger& logger);
    void Finish(Logger& logger);
    void Quit();

    Hardware GetType();

protected:
    virtual void _Run(Logger& logger) = 0;
    virtual void _Finish(Logger& logger) = 0;

    Flag<Flags> _flags;

private:
    Hardware _type;
};
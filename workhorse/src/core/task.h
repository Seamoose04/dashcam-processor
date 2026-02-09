#pragma once

#include <unordered_set>
#include <functional>

#include "core/hardware.h"
#include "core/logger.h"
#include "util/flag.h"

class Task {
public:
    Task(Hardware type);
    bool operator==(const Task& other) const;

    void Run(Logger& logger);
    void Finish(Logger& logger);

    Hardware GetType();

protected:
    virtual void _Run(Logger& logger) = 0;
    virtual void _Finish(Logger& logger) = 0;

private:
    Hardware _type;
};
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

    Task(Hardware type);
    bool operator==(const Task& other) const;

    void Start();
    virtual void Run() = 0;
    void Finish();
    void Quit();

protected:
    virtual void _Start() = 0;
    virtual void _Finish() = 0;

    Hardware _type;
    Flag<Flags> _flags;
};
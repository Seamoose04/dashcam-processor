#pragma once

#include "core/task.h"

class TaskTestCPU : public Task {
public:
    TaskTestCPU();
    void Run(Logger& logger) override;
private:
    void _Start(Logger& logger) override;
    void _Finish(Logger& logger) override;

    Hardware _type = Hardware::Type::CPU;
};
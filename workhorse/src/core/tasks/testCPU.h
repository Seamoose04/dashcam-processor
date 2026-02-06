#pragma once

#include "core/task.h"

class TaskTestCPU : public Task {
public:
    TaskTestCPU() = default;
    void Run() override;
private:
    void _Start() override;
    void _Finish() override;

    Hardware _type = Hardware::Type::CPU;
};
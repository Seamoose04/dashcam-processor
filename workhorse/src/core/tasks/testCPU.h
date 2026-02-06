#pragma once

#include "core/task.h"

class TaskTestCPU : public Task {
public:
    TaskTestCPU();
    void Run() override;
private:
    void _Start() override;
    void _Finish() override;

    Hardware _type = Hardware::Type::CPU;
};
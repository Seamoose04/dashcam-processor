#pragma once

#include "core/task.h"

class TaskTestCPU : public Task {
public:
    TaskTestCPU() = default;
    void Prepare() override;
    void Run() override;
    void Finish() override;
    void Stop(bool immediate=false) override;
};
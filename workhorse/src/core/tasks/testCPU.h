#pragma once

#include "core/task.h"

class TaskTestCPU : public Task {
public:
    TaskTestCPU();
private:
    void _Run() override;
    void _Finish() override;
};
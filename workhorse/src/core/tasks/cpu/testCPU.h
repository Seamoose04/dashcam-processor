#pragma once

#include "core/tasks/cpu.h"

class TaskTestCPU : public TaskCPU {
public:
    TaskTestCPU();
private:
    void _Run() override;
    void _Finish() override;
};
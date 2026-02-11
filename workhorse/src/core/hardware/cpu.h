#pragma once

#include "core/hardware.h"

class CPU : public Hardware {
public:
    CPU();
    void Process(std::shared_ptr<Task> task, Logger* logger, std::shared_ptr<TaskQueue> queue) const override;
};
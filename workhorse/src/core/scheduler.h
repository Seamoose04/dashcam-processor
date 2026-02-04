#pragma once

#include "core/hardware.h"
#include "core/task.h"

struct SchedulerConfig {
    unsigned int max_tasks;
    Hardware hardware_type;
};

class Scheduler {
public:
    Scheduler(SchedulerConfig conf);

private:
    unsigned int _max_tasks;
    Hardware _hardware_type;
};
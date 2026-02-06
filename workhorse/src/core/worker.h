#pragma once

#include <memory>

#include "core/hardware.h"
#include "core/task.h"
#include "core/taskQueue.h"
#include "util/flag.h"

class Worker {
public:
    enum class Flags {
        Stop,
        Quit
    };

    Worker(Hardware type);
    void Work(std::shared_ptr<TaskQueue> queue);
    void Stop();
    void Quit();

private:
    Hardware _type;
    Flag<Flags> _flags;
    std::shared_ptr<TaskQueue> _queue;
    std::shared_ptr<Task> _current_task;
};
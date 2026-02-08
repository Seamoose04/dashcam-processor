#pragma once

#include <filesystem>
#include <memory>

#include "core/hardware.h"
#include "core/logger.h"
#include "core/task.h"
#include "core/taskQueue.h"
#include "util/flag.h"

class Worker {
public:
    enum class Flags {
        Idle,
        Stop,
        Quit
    };

    Worker(Hardware type, Logger::Config logger_conf);
    void Work(std::shared_ptr<TaskQueue> queue);
    void Stop();
    void Quit();

    bool GetIsIdle();

private:
    Hardware _type;
    Flag<Flags> _flags;
    std::shared_ptr<TaskQueue> _queue;
    std::shared_ptr<Task> _current_task;
	Logger _logger;
};

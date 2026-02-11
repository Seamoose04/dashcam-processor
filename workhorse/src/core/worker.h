#pragma once

#include <filesystem>
#include <memory>
#include <vector>

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
    };

    Worker(std::vector<std::shared_ptr<Hardware>> types, Logger::Config logger_conf);
    void Work(std::shared_ptr<TaskQueue> queue);
    void Stop();

    bool GetIsIdle();

private:
    std::vector<std::shared_ptr<Hardware>> _types;
    Flag<Flags> _flags;
    std::shared_ptr<TaskQueue> _queue;
    std::shared_ptr<Task> _current_task;
	std::unique_ptr<Logger> _logger;
};

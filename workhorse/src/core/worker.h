#pragma once

#include <filesystem>
#include <memory>
#include <vector>
#include <mutex>
#include <semaphore>

#include "core/hardware.h"
#include "core/logger.h"
#include "core/task.h"
#include "core/taskQueue.h"
#include "util/flag.h"

class Worker {
public:
    enum class Flags {
        Idle,
        Stop
    };

    Worker(Logger::Config logger_conf);
    void Work(std::shared_ptr<TaskQueue> queue);
    void Stop();
    void SetType(std::unique_ptr<Hardware> type);

    bool GetIsIdle();

private:
    Flag<Flags> _flags;
    std::shared_ptr<TaskQueue> _queue;
    std::shared_ptr<Task> _task;
	std::unique_ptr<Logger> _logger;
    std::unique_ptr<Hardware> _type;
    std::binary_semaphore _signal{0};
};

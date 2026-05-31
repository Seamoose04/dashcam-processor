#pragma once

#include <condition_variable>
#include <memory>
#include <mutex>
#include <atomic>

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
	const Hardware* GetType() const;

    bool GetIsIdle();

private:
    Flag<Flags> _flags;
	std::atomic<size_t> _pending_subscription;
    std::shared_ptr<TaskQueue> _queue;
    std::shared_ptr<Task> _task;
	std::unique_ptr<Logger> _logger;
    std::unique_ptr<Hardware> _type;
	std::mutex _type_mutex;
    std::condition_variable _cv;
};

#pragma once

#include <vector>
#include <thread>

#include "core/worker.h"
#include "core/logger.h"
#include "core/taskQueue.h"
#include "util/flag.h"

class Scheduler {
public:
    enum class Flags {
        Stop,
        Quit
    };
    Scheduler(unsigned int num_workers, Logger::Config log_conf);
    void Run(std::shared_ptr<TaskQueue> task_queue);
    void Quit();
    void Stop();
    bool StopRequested();

private:
    std::vector<std::unique_ptr<Worker>> _workers;
    std::vector<std::thread> _worker_threads;
    Flag<Flags> _flags;
};

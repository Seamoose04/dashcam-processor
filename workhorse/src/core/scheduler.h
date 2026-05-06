#pragma once

#include <vector>
#include <unordered_map>
#include <thread>
#include <atomic>

#include "core/config.h"
#include "core/worker.h"
#include "core/logger.h"
#include "core/taskQueue.h"
#include "core/resources.h"
#include "util/service.h"

class Scheduler : public Service {
public:
    Scheduler(Config conf, Logger::Config worker_log_conf, Logger::Config log_conf);
    void Run(std::shared_ptr<TaskQueue> task_queue);
    void Stop();

private:
	float _available_vram;
	Logger _logger;
    std::vector<std::unique_ptr<Worker>> _workers;
    std::vector<std::thread> _worker_threads;
	std::unordered_map<std::string, Resources> _resources;
	std::atomic<bool> _quit{false};
};

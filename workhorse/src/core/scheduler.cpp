#include "scheduler.h"

#include <format>

Scheduler::Scheduler(unsigned int num_workers, Logger::Config log_conf) {
    _workers.reserve(num_workers);

    for (unsigned int i = 0; i < num_workers; i++) {
        Logger::Config worker_log_conf = log_conf;
        worker_log_conf.path /= std::format("worker{}.txt", i);
        _workers.emplace_back(log_conf);
    }
}

void Scheduler::Run(std::shared_ptr<TaskQueue> task_queue) {
    std::shared_ptr<TaskQueue> tasks = std::move(task_queue);
    _worker_threads.reserve(_workers.size());
    for (auto& worker : _workers) {
        _worker_threads.emplace_back(&Worker::Work, &worker, tasks);
    }

    while (!_flags.Get(Flags::Quit)) {
        if (tasks->GetInProgressTasks() == 0) {
            std::unordered_map<std::string, unsigned int> counts = tasks->GetTaskCounts();
            unsigned int total = 0;
            for (auto count : counts) {
                if (count.second > 0) {
                    total += count.second;
                    break;
                }
            }
            if (total == 0) {
                break;
            }
        }
    }

    _flags.Add(Flags::Stop);
}

void Scheduler::Stop() {
    for (auto& worker : _workers) {
        worker.Stop();
    }
    // TODO: Notify all
    for (auto& worker_thread : _worker_threads) {
        if (worker_thread.joinable()) {
            worker_thread.join();
        }
    }
}

void Scheduler::Quit() {
    _flags.Add(Flags::Quit);
}

bool Scheduler::StopRequested() {
    return _flags.Get(Flags::Stop);
}
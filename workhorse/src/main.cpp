#include <cstdlib>

#include <vector>
#include <memory>
#include <thread>

#include "core/worker.h"
#include "core/hardware.h"
#include "core/taskQueue.h"
#include "core/tasks/testCPU.h"

#define MAX_CPU_WORKERS 4

int main() {
    std::vector<Worker> workers;
    workers.reserve(MAX_CPU_WORKERS);
    for (int i = 0; i < MAX_CPU_WORKERS; i++) {
        workers.emplace_back(Hardware::Type::CPU);
    }

    std::shared_ptr<TaskQueue> tasks = std::make_shared<TaskQueue>();
    std::vector<std::thread> worker_threads;

    worker_threads.reserve(workers.size());
    for (auto& worker : workers) {
        worker_threads.emplace_back(&Worker::Work, &worker, tasks);
    }
    
    for (unsigned int i = 0; i < 128; i++) {
        tasks->AddTask(Hardware::Type::CPU, std::make_unique<TaskTestCPU>());
    }

    while (tasks->GetInProgressTasks() + tasks->GetUnclaimedTasks() > 0) {
        std::this_thread::sleep_for(std::chrono::milliseconds(1000));
    }

    for (auto& worker : workers) {
        worker.Stop();
    }

    tasks->NotifyAll();

    for (auto& worker_thread : worker_threads) {
        if (worker_thread.joinable()) {
            worker_thread.join();
        }
    }

    return EXIT_SUCCESS;
}
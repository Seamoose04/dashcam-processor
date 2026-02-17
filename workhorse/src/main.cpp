#include <cstdlib>
#include <vector>
#include <memory>
#include <thread>
#include <format>
#include <opencv2/opencv.hpp>

#include "core/worker.h"
#include "core/logger.h"
#include "core/hardware/cpu.h"
#include "core/hardware/yoloV7.h"
#include "core/taskQueue.h"
#include "core/tasks/cpu/splitVideo.h"
#include "core/config.h"
#include "core/tui.h"

int main() {
    Config config;
    config.LOG_LEVEL = Logger::Level::Warn;
    config.MAX_CPU_WORKERS = 8;
    config.MAX_GPU_WORKERS = 12;

    Logger::Config logger_conf;
    logger_conf.level = config.LOG_LEVEL;
    logger_conf.path = "logs/main.txt";
    Logger logger(logger_conf);

    logger.Log(Logger::Level::Info, "Main::Info Initializing...\n");

    std::vector<std::unique_ptr<Worker>> cpu_workers;
    cpu_workers.reserve(config.MAX_CPU_WORKERS);

    std::vector<std::unique_ptr<Worker>> gpu_workers;
    gpu_workers.reserve(config.MAX_GPU_WORKERS);

    for (int i = 0; i < config.MAX_CPU_WORKERS; i++) {
        Logger::Config conf;
        conf.level = config.LOG_LEVEL;
        conf.path = std::format("logs/cpu_workers/worker{}.txt", i);

        std::vector<std::shared_ptr<Hardware>> hardware;
        hardware.push_back(Registry<Hardware>::Instance().Create("CPU"));
        cpu_workers.push_back(std::make_unique<Worker>(std::move(hardware), conf));
    }
    
    for (int i = 0; i < config.MAX_GPU_WORKERS; i++) {
        Logger::Config conf;
        conf.level = config.LOG_LEVEL;
        conf.path = std::format("logs/gpu_workers/worker{}.txt", i);

        std::vector<std::shared_ptr<Hardware>> hardware;
        hardware.push_back(Registry<Hardware>::Instance().Create("YoloV7"));
        hardware.push_back(Registry<Hardware>::Instance().Create("LPR"));
        gpu_workers.push_back(std::make_unique<Worker>(std::move(hardware), conf));
    }

    logger.Log(Logger::Level::Info, std::format("Main::Info Spawned {} cpu workers and {} gpu workers\n", cpu_workers.size(), gpu_workers.size()));

    std::shared_ptr<TaskQueue> tasks = std::make_shared<TaskQueue>();

    std::vector<std::thread> cpu_worker_threads;
    std::vector<std::thread> gpu_worker_threads;

    cpu_worker_threads.reserve(cpu_workers.size());
    for (auto& worker : cpu_workers) {
        cpu_worker_threads.emplace_back(&Worker::Work, worker.get(), tasks);
    }

    gpu_worker_threads.reserve(gpu_workers.size());
    for (auto& worker : gpu_workers) {
        gpu_worker_threads.emplace_back(&Worker::Work, worker.get(), tasks);
    }

    logger.Log(Logger::Level::Info, "Main::Info worker threads started.\n");

    Tui tui(config, tasks);
    std::thread tui_thread(&Tui::Run, &tui);

    // Add videos to process
    tasks->AddTask(std::make_unique<TaskSplitVideo>("tmp/test.mp4"));

    // Start processing
    for (;;) {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));

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
    
    logger.Log(Logger::Level::Info, "Main::Info Stopping...\n");
    
    tui.Exit();
    if (tui_thread.joinable()) {
        tui_thread.join();
    }

    for (auto& worker : cpu_workers) {
        worker->Stop();
    }

    for (auto& worker : gpu_workers) {
        worker->Stop();
    }

    tasks->NotifyAll();

    logger.Log(Logger::Level::Info, "Main::Info Workers stopped.\n");

    for (auto& worker_thread : cpu_worker_threads) {
        if (worker_thread.joinable()) {
            worker_thread.join();
        }
    }

    for (auto& worker_thread : gpu_worker_threads) {
        if (worker_thread.joinable()) {
            worker_thread.join();
        }
    }

    logger.Log(Logger::Level::Info, "Main::Info Stopped.\n");

    return EXIT_SUCCESS;
}

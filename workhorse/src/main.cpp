#include <cstdlib>
#include <vector>
#include <memory>
#include <thread>
#include <format>
#include <opencv2/opencv.hpp>

#include "core/worker.h"
#include "core/logger.h"
#include "core/hardware.h"
#include "core/taskQueue.h"
#include "core/tasks/splitVideo.h"

#define MAX_CPU_WORKERS 4
#define MAX_GPU_WORKERS 4
#define LOG_LEVEL Logger::Level::Info

int main() {
    Logger::Config logger_conf;
    logger_conf.level = LOG_LEVEL;
    logger_conf.path = "logs/main.txt";
    Logger logger(logger_conf);

    logger.Log(Logger::Level::Info, "Main::Info Initializing...\n");

    std::vector<std::unique_ptr<Worker>> cpu_workers;
    cpu_workers.reserve(MAX_CPU_WORKERS);

    std::vector<std::unique_ptr<Worker>> gpu_workers;
    gpu_workers.reserve(MAX_GPU_WORKERS);

    for (int i = 0; i < MAX_CPU_WORKERS; i++) {
        Logger::Config conf;
        conf.level = LOG_LEVEL;
        conf.path = std::format("logs/cpu_workers/worker{}.txt", i);
        cpu_workers.push_back(std::make_unique<Worker>(Hardware::Type::CPU, conf));
    }
    
    for (int i = 0; i < MAX_GPU_WORKERS; i++) {
        Logger::Config conf;
        conf.level = LOG_LEVEL;
        conf.path = std::format("logs/gpu_workers/worker{}.txt", i);
        gpu_workers.push_back(std::make_unique<Worker>(Hardware::Type::GPU, conf));
    }

    logger.Log(Logger::Level::Info, std::format("Main::Info Spawned {} cpu workers and {} gpu workers\n", cpu_workers.size(), gpu_workers.size()));

    std::shared_ptr<TaskQueue> tasks = std::make_shared<TaskQueue>();

    std::vector<std::thread> cpu_worker_threads;
    std::vector<std::thread> gpu_worker_threads;

    cpu_worker_threads.reserve(cpu_workers.size());
    for (auto& worker : cpu_workers) {
        cpu_worker_threads.emplace_back(&Worker::Work, &(*worker), tasks);
    }

    gpu_worker_threads.reserve(gpu_workers.size());
    for (auto& worker : gpu_workers) {
        gpu_worker_threads.emplace_back(&Worker::Work, &(*worker), tasks);
    }

    logger.Log(Logger::Level::Info, "Main::Info worker threads started.\n");

    // Add videos to process
    cv::VideoCapture video("tmp/test.mp4");
    tasks->AddTask(std::make_unique<TaskSplitVideo>(std::make_shared<cv::VideoCapture>(video)));

    // Start processing
    while (tasks->GetInProgressTasks() + tasks->GetUnclaimedTasks() > 0) {
        std::this_thread::sleep_for(std::chrono::milliseconds(1000));
    }
    
    logger.Log(Logger::Level::Info, "Main::Info Stopping...\n");

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

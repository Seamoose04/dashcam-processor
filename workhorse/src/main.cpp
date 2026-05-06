#include <cstdlib>
#include <memory>
#include <semaphore>
#include <thread>
#include <format>
#include <opencv2/opencv.hpp>

#include "core/logger.h"
#include "core/scheduler.h"
#include "core/taskQueue.h"
#include "core/tasks/cpu/splitVideo.h"
#include "core/tasks/cpu/testCPU.h"
#include "core/config.h"
#include "core/tui.h"

int main() {
    Config config;
    config.LOG_LEVEL = Logger::Level::Info;
    config.MAX_WORKERS = 64;
	config.AVAILABLE_VRAM = 20.0f;

    Logger::Config logger_conf;
    logger_conf.level = config.LOG_LEVEL;
    logger_conf.path = "logs/main.txt";
    Logger logger(logger_conf);

    logger.Log(Logger::Level::Info, "Main::Info Initializing...\n");

    Logger::Config worker_logger_config;
    worker_logger_config.level = config.LOG_LEVEL;
    worker_logger_config.path = "logs/workers";
	Logger::Config scheduler_logger_config;
	scheduler_logger_config.level = config.LOG_LEVEL;
	scheduler_logger_config.path = "logs/scheduler.txt";
    Scheduler scheduler(config, worker_logger_config, scheduler_logger_config);

    logger.Log(Logger::Level::Info, std::format("Main::Info Spawned {} workers\n", config.MAX_WORKERS));

    // Start processing
    std::shared_ptr<TaskQueue> tasks = std::make_shared<TaskQueue>();
    Tui tui(config, tasks);
    std::thread tui_thread(&Tui::Run, &tui);
    std::thread scheduler_thread(&Scheduler::Run, &scheduler, tasks);

    // Add videos to process
    tasks->AddTask(std::make_unique<TaskSplitVideo>("tmp/test.mp4"));
	// tasks->AddTask(std::make_unique<TaskTestCPU>());

    // Wait
	std::binary_semaphore shutdown(0);
	auto trigger = [&shutdown]{ shutdown.release(); };
	tui.onComplete.Subscribe(trigger);
	scheduler.onComplete.Subscribe(trigger);
	shutdown.acquire();

	// Stop + Cleanup
	logger.Log(Logger::Level::Info, "Main::Info Stopping...\n");
	tui.Stop();
	scheduler.Stop();

    if (tui_thread.joinable()) {
        tui_thread.join();
    }
    if (scheduler_thread.joinable()) {
        scheduler_thread.join();
    }

	// Finished
    logger.Log(Logger::Level::Info, "Main::Info Stopped.\n");

    return EXIT_SUCCESS;
}

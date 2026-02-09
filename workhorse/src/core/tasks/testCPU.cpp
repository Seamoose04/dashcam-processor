#include "testCPU.h"

#include <format>

TaskTestCPU::TaskTestCPU() : Task(Hardware::Type::CPU) { }

void TaskTestCPU::_Run(Logger& logger) {
    logger.Log(Logger::Level:: Info, "TaskTestCPU::Info Starting...\n");
    for (int i = 0; i <= 100000; i++) {
        if (i % 10000 == 0) {
            logger.Log(Logger::Level::Info, std::format("TaskTestCPU::Info Progress: {}/10\n", i / 10000));
        }
    }
}

void TaskTestCPU::_Finish(Logger& logger) {
    logger.Log(Logger::Level::Info, "TaskTestCPU::Info Complete\n");
}
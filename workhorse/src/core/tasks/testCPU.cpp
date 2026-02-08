#include "testCPU.h"

#include <iostream>
#include <format>

TaskTestCPU::TaskTestCPU() : Task(_type) { }

void TaskTestCPU::_Start(Logger& logger) {
    logger.Log(Logger::Level::Info, "TaskTestCPU::Info Starting...\n");
}

void TaskTestCPU::Run(Logger& logger) {
    for (int i = 0; i <= 100000; i++) {
        if (_flags.Get(Flags::Quit)) {
            logger.Log(Logger::Level::Warn, "TaskTestCPU::Warn Stopped early\n");
            return;
        }
        if (i % 10000 == 0) {
            logger.Log(Logger::Level::Info, std::format("TaskTestCPU::Info Progress: {}/10\n", i / 10000));
        }
    }
    Finish(logger);
}

void TaskTestCPU::_Finish(Logger& logger) {
    logger.Log(Logger::Level::Info, "TaskTestCPU::Info Complete\n");
}
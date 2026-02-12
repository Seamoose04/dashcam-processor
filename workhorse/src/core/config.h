#pragma once

#include "core/logger.h"

struct Config {
    unsigned int MAX_CPU_WORKERS;
    unsigned int MAX_GPU_WORKERS;
    Logger::Level LOG_LEVEL;
};
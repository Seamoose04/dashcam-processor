#pragma once

#include <filesystem>
#include <string>

#include "core/logger.h"  // for Logger::Level

// .env-style configuration for the workhorse processor, loaded via dotenv.h — a
// vendored single-header lib (see FetchContent in CMakeLists.txt).
//
// Any value left at its sentinel (0 / "") triggers auto-detection from hardware,
// so this file is optional: run without one and sensible defaults are derived.
struct Config {
    unsigned int MAX_WORKERS = 0;            // 0 => std::thread::hardware_concurrency()
    float AVAILABLE_VRAM_GB = 0.0f;          // GB; 0 => read from nvidia-smi (minus headroom)
    Logger::Level LOG_LEVEL = Logger::Level::Warn;
    std::filesystem::path LOG_DIR = "logs";

    bool loaded_from_file = false;           // whether a config file was found on disk

    // Load config from `filename` (default "config.env", or $WORKHORSE_CONFIG if set).
    // Falls back to auto-detection for any value left at its sentinel.
    static Config load(const std::filesystem::path& filename = "config.env");
};

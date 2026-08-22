// Standalone verification of Config::load with the vendored dotenv.h loader.
// No GPU/sudo needed — just confirms .env parsing + fallbacks behave as chosen.
#include <cassert>
#include <cmath>
#include <cstdio>
#include <iostream>
#include "core/config.h"

int main() {
    const char* FIX = "tests/fixtures/config.env";

    // load(): clean config file parses correctly
    auto cfg1 = Config::load(FIX);
    assert(cfg1.loaded_from_file == true);
    assert(cfg1.MAX_WORKERS == 24);
    assert(std::abs(cfg1.AVAILABLE_VRAM_GB - 8.0f) < 0.01f);   // parsed from file, not auto-detected
    assert(cfg1.LOG_LEVEL == Logger::Level::Info);

    // load(): missing file => sentinels + hardware fallbacks
    auto cfg2 = Config::load("does_not_exist.env");
    assert(cfg2.loaded_from_file == false);
    assert(cfg2.MAX_WORKERS > 0);                       // hardware_concurrency fallback
    assert(cfg2.AVAILABLE_VRAM_GB > 0.0f);              // nvidia-smi -> default fallback

    // dotenv also consults OS environment variables when a key is absent from the file:
    // nomax.env omits max_workers, so an exported value flows through.
    setenv("max_workers", "128", 1);
    auto cfg3 = Config::load("tests/fixtures/nomax.env");
    assert(cfg3.MAX_WORKERS == 128);

    std::cout << "[config] load tests passed\n";
    return 0;
}

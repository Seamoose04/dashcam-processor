#include "core/config.h"

#include <algorithm>
#include <cstdio>
#include <thread>

#include "dotenv.h"   // vendored single-header .env loader (fetched via FetchContent in CMakeLists.txt)

namespace {

std::string trim(const std::string& s) {
    const char* ws = " \t\r\n";
    const auto start = s.find_first_not_of(ws);
    if (start == std::string::npos) return "";
    const auto end = s.find_last_not_of(ws);
    return s.substr(start, end - start + 1);
}

// Convert a string to Logger::Level. Case-insensitive; unknown -> Warn.
Logger::Level level_from_string(const std::string& raw) {
    std::string v = trim(raw);
    std::transform(v.begin(), v.end(), v.begin(), [](unsigned char c) { return (char)std::tolower(c); });
    if (v == "none")   return Logger::Level::None;
    if (v == "error")  return Logger::Level::Error;
    if (v == "warn" || v == "warning") return Logger::Level::Warn;
    if (v == "info")   return Logger::Level::Info;
    return Logger::Level::Warn;
}

// Read available VRAM from nvidia-smi. Returns -1 on any failure (=> auto-detect fallback).
float detect_vram_gb() {
    FILE* pipe = popen(
        "nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -n1",
        "r");
    if (!pipe) return -1.0f;

    char buffer[256];
    std::string result;
    while (fgets(buffer, sizeof(buffer), pipe) != nullptr) {
        result += buffer;
    }
    pclose(pipe);

    try {
        float mb = std::stof(trim(result));  // e.g. "24576"
        if (mb > 0.0f) return mb / 1024.0f * 0.90f;  // convert to GB, keep 10% headroom
    } catch (...) {
        return -1.0f;
    }
    return -1.0f;
}

} // namespace

Config Config::load(const std::filesystem::path& filename) {
    std::filesystem::path path = filename;
    if (filename == "config.env") {
        // Allow override via env var without hard-coding a location.
        if (const char* env = std::getenv("WORKHORSE_CONFIG")) {
            if (std::filesystem::exists(env)) path = env;
        }
    }

    dotenv env(path.string());  // parses the .env file (also falls back to OS env vars)

    Config cfg;
    cfg.loaded_from_file = std::filesystem::exists(path);

    // MAX_WORKERS: config value wins; fall back to CPU count if neither provided one.
    if (const std::string v = env.get("max_workers"); !v.empty()) {
        try { cfg.MAX_WORKERS = static_cast<unsigned int>(std::stoul(v)); }
        catch (...) {}
    }
    if (cfg.MAX_WORKERS == 0) cfg.MAX_WORKERS = std::thread::hardware_concurrency() > 0 ? std::thread::hardware_concurrency() : 4;

    // AVAILABLE_VRAM_GB: config value wins; fall back to nvidia-smi then default.
    if (const std::string v = env.get("available_vram_gb"); !v.empty()) {
        try { cfg.AVAILABLE_VRAM_GB = static_cast<float>(std::stof(v)); }
        catch (...) {}
    }
    if (cfg.AVAILABLE_VRAM_GB <= 0.0f) {
        float detected = detect_vram_gb();
        cfg.AVAILABLE_VRAM_GB = detected > 0.0f ? detected : 8.0f;  // sane fallback for unknown box
    }

    // LOG_LEVEL: string -> enum.
    if (const std::string v = env.get("log_level"); !v.empty()) {
        cfg.LOG_LEVEL = level_from_string(v);
    }

    // LOG_DIR: relative to config file's directory so logs follow wherever the file lives.
    if (const std::string v = env.get("log_dir"); !v.empty()) {
        cfg.LOG_DIR = path.parent_path() / v;  // resolve relative to config location
    }

    return cfg;
}

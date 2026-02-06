#pragma once

#include <string>
#include <filesystem>
#include <fstream>

class Logger {
public:
    enum class Level {
        None,
        Error,
        Warn,
        Info
    };

    Logger(std::filesystem::path log_path, Level level);
    ~Logger();

    void Log(Level level, std::string msg);

private:
    std::filesystem::path _log_path;
    std::ofstream _out_file;
    Level _level;
};
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

	struct Config {
		std::filesystem::path path;
		Level level;
	};

    Logger(Config conf);
    ~Logger();

    void Log(Level level, std::string msg);

private:
    std::filesystem::path _log_path;
    std::ofstream _out_file;
    Level _level;
};

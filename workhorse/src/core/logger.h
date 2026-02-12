#pragma once

#include <string>
#include <filesystem>
#include <fstream>
#include <thread>
#include <mutex>

#include "util/flag.h"

class Logger {
public:
    enum class Level {
        None,
        Error,
        Warn,
        Info
    };

    enum class Flags {
        Stop
    };

	struct Config {
		std::filesystem::path path;
		Level level;
	};

    Logger(Config conf);
    ~Logger();

    void Log(Level level, std::string msg);
    std::filesystem::path GetFIFOPath();
    static std::string LevelToString(Level level);

private:
    void _ReadFIFO();

    Level _level;
    std::filesystem::path _log_path;
    std::ofstream _out_file;
    std::filesystem::path _fifo_path;
    std::thread _fifo_reader_thread;
    std::mutex _logging_mutex;
    Flag<Flags> _flags;
};

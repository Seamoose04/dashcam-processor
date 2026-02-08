#include "logger.h"

Logger::Logger(Config conf) {
    _level = conf.level;
    _log_path = conf.path;
    _out_file = std::ofstream(_log_path, std::ios_base::app);
}

void Logger::Log(Level level, std::string msg) {
    if (static_cast<int>(level) <= static_cast<int>(_level)) {
        _out_file << msg;
    }
}

Logger::~Logger() {
    if (_out_file.is_open()) {
        _out_file.close();
    }
}

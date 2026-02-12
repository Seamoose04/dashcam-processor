#include "logger.h"

#include <sys/stat.h>
#include <fcntl.h>

Logger::Logger(Config conf) {
    _level = conf.level;
    _log_path = conf.path;
    _out_file = std::ofstream(_log_path, std::ios_base::app);

    _fifo_path = _log_path.parent_path() / ("fifo_" + _log_path.filename().string());
    std::filesystem::remove(_fifo_path);
    if (mkfifo(_fifo_path.c_str(), 0666) != 0) {
        Log(Level::Error, "Logger::Error Failed to create FIFO.\n");
    }

    _fifo_reader_thread = std::thread([this]() { _ReadFIFO(); });
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
}

void Logger::Log(Level level, std::string msg) {
    std::scoped_lock<std::mutex> logging_lock(_logging_mutex);
    if (static_cast<int>(level) <= static_cast<int>(_level)) {
        _out_file << msg;
    }
}

std::filesystem::path Logger::GetFIFOPath() {
    return _fifo_path;
}

void Logger::_ReadFIFO() {
    int fd = open(_fifo_path.c_str(), O_RDONLY | O_NONBLOCK);
    if (fd < 0) {
        Log(Level::Error, "Logger::Error Failed to open FIFO.");
        return;
    }

    char buffer[4096];
    std::string line_buffer;

    while (!_flags.Get(Flags::Stop)) {
        fd_set read_fds;
        FD_ZERO(&read_fds);
        FD_SET(fd, &read_fds);
        
        struct timeval timeout;
        timeout.tv_sec = 0;
        timeout.tv_usec = 100000;
        
        int ret = select(fd + 1, &read_fds, nullptr, nullptr, &timeout);

        if (ret < 0) {
            Log(Level::Error, "Logger::Error select failed.\n");
            break;
        } else if (ret == 0) {
            continue;
        }

        ssize_t n = read(fd, buffer, sizeof(buffer));

        if (n < 0) {
            if (errno == EAGAIN || errno == EWOULDBLOCK) {
                continue;
            }
            Log(Level::Error, "Logger::Error Failed to read from FIFO.\n");
            break;
        } else if (n == 0) {
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            continue;
        }

        for (ssize_t i = 0; i < n; i++) {
            if (buffer[i] == '\n') {
                if (!line_buffer.empty()) {
                    Log(Level::Info, "OutsideProcess::Info " + line_buffer + '\n');
                    line_buffer.clear();
                }
            } else {
                line_buffer += buffer[i];
            }
        }
    }

    if (!line_buffer.empty()) {
        Log(Level::Info, "OutsideProcess::Info " + line_buffer + '\n');
    }

    close(fd);
}

std::string Logger::LevelToString(Level level) {
    switch (level)
    {
    case Level::None:
        return "None";
    
    case Level::Error:
        return "Error";
    
    case Level::Warn:
        return "Warn";
    
    case Level::Info:
        return "Info";
    }

    return "Null";
}

Logger::~Logger() {
    _flags.Add(Flags::Stop);

    int fd = open(_fifo_path.c_str(), O_WRONLY | O_NONBLOCK);
    if (fd >= 0) {
        close(fd);
    }

    if (_fifo_reader_thread.joinable()) {
        _fifo_reader_thread.join();
    }

    std::filesystem::remove(_fifo_path);

    if (_out_file.is_open()) {
        _out_file.close();
    }
}

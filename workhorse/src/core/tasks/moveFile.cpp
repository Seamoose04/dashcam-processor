#include "moveFile.h"

#include <format>

TaskMoveFile::TaskMoveFile(std::filesystem::path source, std::filesystem::path destination, bool remove_src) : Task(Hardware::Type::CPU) {
    _src_path = source;
    _dest_path = destination;
    _rm_src = false;
}

void TaskMoveFile::_Run() {
    _logger->Log(Logger::Level::Info, std::format("TaskMoveFile::Info Moving file '{}' to '{}'\n", _src_path.relative_path(), _dest_path.relative_path()));
    std::filesystem::copy_file(_src_path, _dest_path);

    if (_rm_src) {
        bool success = std::filesystem::remove(_src_path);
        if (success) {
            _logger->Log(Logger::Level::Info, std::format("TaskMoveFile::Info File '{}' deleted.\n", _src_path.relative_path()));
        } else {
            _logger->Log(Logger::Level::Warn, std::format("TaskMoveFile::Warn File '{}' was unable to be deleted.\n", _src_path.relative_path()));
        }
    }
}

void TaskMoveFile::_Finish() {
    _logger->Log(Logger::Level::Info, "TaskMoveFile::Info File moved.\n");
}
#pragma once

#include <filesystem>

#include "core/tasks/cpu.h"

class TaskMoveFile : public TaskCPU {
public:
    TaskMoveFile(std::filesystem::path source, std::filesystem::path destination, bool remove_src = false);

private:
    void _Run() override;
    void _Finish() override;

    std::filesystem::path _src_path;
    std::filesystem::path _dest_path;
    bool _rm_src;
};
#pragma once

#include <filesystem>
#include <opencv2/opencv.hpp>

#include "core/tasks/cpu.h"
#include "util/flag.h"

class TaskSplitVideo : public TaskCPU {
public:
    enum class Flags {
        Stop,
        Pause
    };
    TaskSplitVideo(std::filesystem::path video_path);

private:
    void _Run() override;
    void _Finish() override;

    std::filesystem::path _video_path;
    Flag<Flags> _flags;
};
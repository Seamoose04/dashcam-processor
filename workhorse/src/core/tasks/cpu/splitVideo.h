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
    TaskSplitVideo(std::shared_ptr<cv::VideoCapture> video);

private:
    void _Run() override;
    void _Finish() override;

    std::shared_ptr<cv::VideoCapture> _video;
    Flag<Flags> _flags;
};
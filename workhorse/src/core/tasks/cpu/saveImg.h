#pragma once

#include <opencv2/opencv.hpp>
#include <filesystem>

#include "core/tasks/cpu.h"

class TaskSaveImg : public TaskCPU {
public:
    TaskSaveImg(cv::Mat img, std::filesystem::path path);

private:
    void _Run() override;
    void _Finish() override;

    cv::Mat _img;
    std::filesystem::path _path;
};
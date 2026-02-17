#pragma once

#include <opencv2/opencv.hpp>
#include <filesystem>
#include <memory>

#include "core/tasks/cpu.h"

class TaskSaveImg : public TaskCPU {
public:
    TaskSaveImg(std::shared_ptr<cv::Mat> img, std::filesystem::path path);

private:
    void _Run() override;
    void _Finish() override;

    std::shared_ptr<cv::Mat> _img;
    std::filesystem::path _path;
};
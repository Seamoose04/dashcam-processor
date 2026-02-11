#pragma once

#include <DarkHelp.hpp>
#include <memory>

#include "core/task.h"

class TaskDetectCars : public Task {
public:
    TaskDetectCars(std::shared_ptr<cv::Mat> img_to_process, std::string video_id);

private:
    void _Run() override;
    void _Finish() override;

    std::shared_ptr<cv::Mat> _img;
    std::string _video_id;
};
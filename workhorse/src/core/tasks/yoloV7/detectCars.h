#pragma once

#include <DarkHelp.hpp>
#include <memory>

#include "core/tasks/yoloV7.h"

class TaskDetectCars : public TaskYoloV7 {
public:
    TaskDetectCars(std::shared_ptr<cv::Mat> img_to_process, std::string video_id);

private:
    void _Run() override;
    void _Finish() override;

    std::shared_ptr<cv::Mat> _img;
    std::string _video_id;
};
#pragma once

#include <DarkHelp.hpp>
#include <memory>

#include "core/tasks/lpr.h"
#include "core/car.h"

class TaskDetectLicensePlates : public TaskLPR {
public:
    TaskDetectLicensePlates(std::shared_ptr<cv::Mat> img_to_process, Car car);

private:
    void _Run() override;
    void _Finish() override;

    std::shared_ptr<cv::Mat> _img;
    Car _car;
};
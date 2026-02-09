#pragma once

#include <DarkHelp.hpp>

#include "core/task.h"

class TaskDetectCars : public Task {
public:
    TaskDetectCars(cv::Mat img_to_process);

private:
    void _Run() override;
    void _Finish() override;

    cv::Mat _img;
};
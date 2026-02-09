#pragma once

#include <DarkHelp.hpp>

#include "core/task.h"

class TaskTestDarknet : public Task {
public:
    TaskTestDarknet(cv::Mat img_to_process);

private:
    void _Run(Logger& logger) override;
    void _Finish(Logger& logger) override;

    cv::Mat _img;
};
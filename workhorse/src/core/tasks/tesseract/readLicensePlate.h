#pragma once

#include <opencv2/opencv.hpp>
#include <memory>

#include "core/tasks/tesseract.h"
#include "core/car.h"

class TaskReadLicensePlate : public TaskTesseract {
public:
    TaskReadLicensePlate(std::shared_ptr<cv::Mat> lp_img, Car car);

private:
    void _Run() override;
    void _Finish() override;

    std::shared_ptr<cv::Mat> _img;
    Car _car;
};
#include "detectLicensePlates.h"

#include "core/tasks/tesseract/readLicensePlate.h"

TaskDetectLicensePlates::TaskDetectLicensePlates(std::shared_ptr<cv::Mat> img_to_process, Car car) {
    _img = img_to_process;
    _car = car;
}

void TaskDetectLicensePlates::_Run() {
    _logger->Log(Logger::Level::Info, "TaskDetectLicensePlates::Info Setting config...\n");

    _nn->config.threshold = 0.4;

    _logger->Log(Logger::Level::Info, "TaskDetectLicensePlates::Info Processing Image...\n");
    const auto result = _nn->predict(*_img);

    for (const auto& prediction : result) {
        if (prediction.best_probability >= 0.4) {
            cv::Mat crop;
            (*_img)(prediction.rect).copyTo(crop);

            _logger->Log(Logger::Level::Info, "TaskDetectLicensePlates::Info License plate found! Attempting to read...\n");
            _spawn_cb(std::make_unique<TaskReadLicensePlate>(std::make_shared<cv::Mat>(crop), _car));
        }
    }
}

void TaskDetectLicensePlates::_Finish() {
    _logger->Log(Logger::Level::Info, "TaskDetectLicensePlates::Info Complete.\n");
}
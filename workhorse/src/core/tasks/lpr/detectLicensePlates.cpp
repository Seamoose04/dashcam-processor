#include "detectLicensePlates.h"

#include "core/tasks/cpu/saveImg.h"

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

            _logger->Log(Logger::Level::Info, "TaskDetectLicensePlates::Info License plate found! Spawning TaskSaveImg.\n");
            _spawn_cb(std::make_unique<TaskSaveImg>(crop, std::format("outputs/{}_{}_{}_plate.png", _car.video, _car.frame, _car.id)));
        }
    }
}

void TaskDetectLicensePlates::_Finish() {
    _logger->Log(Logger::Level::Info, "TaskDetectLicensePlates::Info Complete.\n");
}
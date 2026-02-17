#include "detectCars.h"

#include "core/tasks/lpr/detectLicensePlates.h"
#include "core/car.h"

TaskDetectCars::TaskDetectCars(std::shared_ptr<cv::Mat> img_to_process, std::string video, unsigned int frame) {
    _img = img_to_process;
    _video = video;
    _frame = frame;
}

void TaskDetectCars::_Run() {
    _logger->Log(Logger::Level::Info, "TaskDetectCars::Info Setting config...\n");

    _nn->config.threshold = 0.3;
    _nn->config.include_all_names = false;

    _logger->Log(Logger::Level::Info, "TaskDetectCars::Info Processing Image...\n");
    const auto result = _nn->predict(*_img);

    int car_id = 0;
    for (const auto& prediction : result) {
        if (prediction.best_class == 2) {
            cv::Mat crop;
            (*_img)(prediction.rect).copyTo(crop);

            _logger->Log(Logger::Level::Info, "TaskDetectCars::Info Car found!\n");

            Car car;
            car.video = _video;
            car.frame = _frame;
            car.id = car_id;
            _spawn_cb(std::make_unique<TaskDetectLicensePlates>(std::make_shared<cv::Mat>(crop), car));

            car_id++;
        }
    }
}

void TaskDetectCars::_Finish() {
    _logger->Log(Logger::Level::Info, "TaskDetectCars::Info Complete.\n");
}
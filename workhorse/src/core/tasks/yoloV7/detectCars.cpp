#include "detectCars.h"

#include "core/tasks/cpu/saveImg.h"

TaskDetectCars::TaskDetectCars(std::shared_ptr<cv::Mat> img_to_process, std::string video_id) {
    _img = img_to_process;
    _video_id = video_id;
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

            _logger->Log(Logger::Level::Info, "TaskDetectCars::Info Car found! Spawning TaskSaveImg.\n");
            _spawn_cb(std::make_unique<TaskSaveImg>(crop, std::format("outputs/video{}_car{}.png", _video_id, car_id)));

            car_id++;
        }
    }
}

void TaskDetectCars::_Finish() {
    _logger->Log(Logger::Level::Info, "TaskDetectCars::Info Complete.\n");
}
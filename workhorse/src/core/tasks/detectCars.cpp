#include "detectCars.h"

#include <darknet.hpp>
#include <format>

#include "core/tasks/saveImg.h"

TaskDetectCars::TaskDetectCars(std::shared_ptr<cv::Mat> img_to_process, std::string video_id) : Task(Hardware::Type::GPU) {
    _img = img_to_process;
    _video_id = video_id;
}

void TaskDetectCars::_Run() {
    _logger->Log(Logger::Level::Info, "TaskDetectCars::Info Loading yolov7...\n");
    Darknet::set_output_stream(_logger->GetFIFOPath());
    DarkHelp::Config cfg;
    cfg.cfg_filename = "models/yolov7/yolov7.cfg";
    cfg.weights_filename = "models/yolov7/yolov7.weights";
    cfg.names_filename = "models/yolov7/coco.names";
    cfg.threshold = 0.3;
    cfg.include_all_names = false;
    DarkHelp::NN nn(cfg);

    _logger->Log(Logger::Level::Info, "TaskDetectCars::Info Processing Image...\n");
    const auto result = nn.predict(*_img);

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
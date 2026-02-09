#include "testDarknet.h"
#include <darknet.hpp>

#include <format>

TaskTestDarknet::TaskTestDarknet(cv::Mat img_to_process) : Task(Hardware::Type::GPU) {
    _img = img_to_process;
}

void TaskTestDarknet::_Run() {
    _logger->Log(Logger::Level::Info, "TaskTestDarknet::Info Loading Darknet...\n");
    Darknet::set_output_stream(_logger->GetFIFOPath());
    DarkHelp::Config cfg;
    cfg.cfg_filename = "models/yolov7/yolov7.cfg";
    cfg.weights_filename = "models/yolov7/yolov7.weights";
    cfg.names_filename = "models/yolov7/coco.names";
    cfg.threshold = 0.65;
    cfg.include_all_names = false;
    cfg.annotation_include_duration = false;
    cfg.annotation_auto_hide_labels = false;
    DarkHelp::NN nn(cfg);
    _logger->Log(Logger::Level::Info, "TaskTestDarknet::Info Darknet Loaded.\n");

    _logger->Log(Logger::Level::Info, "TaskTestDarknet::Info Processing Image...\n");
    const auto result = nn.predict(_img);
    cv::Mat output = nn.annotate();
    cv::imwrite("outputs/annotated.png", output);
}

void TaskTestDarknet::_Finish() {
    _logger->Log(Logger::Level::Info, "TaskTestDarknet::Info Complete, file saved to 'outputs/annotated.png'\n");
}
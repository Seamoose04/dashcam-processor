#include "saveImg.h"

TaskSaveImg::TaskSaveImg(cv::Mat img, std::filesystem::path path) : Task(Hardware::Type::CPU) {
    _img = img;
    _path = path;
}

void TaskSaveImg::_Run() {
    _logger->Log(Logger::Level::Info, "TaskSaveImg::Info Saving image...\n");
    cv::imwrite(_path, _img);
}

void TaskSaveImg::_Finish() {
    _logger->Log(Logger::Level::Info, "TaskSaveImg::Info Image saved.\n");
}
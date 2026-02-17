#include "readLicensePlate.h"

#include "core/tasks/cpu/saveImg.h"

TaskReadLicensePlate::TaskReadLicensePlate(std::shared_ptr<cv::Mat> lp_img, Car car) {
    _img = lp_img;
    _car = car;
}

void TaskReadLicensePlate::_Run() {
    _logger->Log(Logger::Level::Info, "TaskReadLicensePlate::Info Setting config...\n");
    _tess->SetPageSegMode(tesseract::PSM_SINGLE_LINE);
    _tess->SetVariable("tessedit_char_whitelist", "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789");

    _logger->Log(Logger::Level::Info, "TaskReadLicensePlate::Info Processing Image...\n");
    _tess->SetImage(_img->data, _img->cols, _img->rows, _img->channels(), _img->step);
    std::string text = _tess->GetUTF8Text();

    text.erase(std::remove_if(text.begin(), text.end(), ::isspace), text.end());
    _car.plate = text;
    
    _logger->Log(Logger::Level::Info, "TaskReadLicensePlate::Info Plate read.\n");
    _spawn_cb(std::make_unique<TaskSaveImg>(_img, std::format("outputs/{}.png", _car.plate)));
}

void TaskReadLicensePlate::_Finish() {
    _logger->Log(Logger::Level::Info, "TaskReadLicensePlate::Info Complete.\n");
}
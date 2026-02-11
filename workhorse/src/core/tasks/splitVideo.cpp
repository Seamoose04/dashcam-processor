#include "splitVideo.h"

#include "core/tasks/detectCars.h"

TaskSplitVideo::TaskSplitVideo(std::shared_ptr<cv::VideoCapture> video) : Task(Hardware::Type::CPU) {
    _video = video;
}

void TaskSplitVideo::_Run() {
    if (!_video->isOpened()) {
        _logger->Log(Logger::Level::Error, "TaskSplitVideo::Error Video not open.\n");
        return;
    }

    unsigned int frame_id = 0;
    while (!_flags.Get(Flags::Stop)) {
        cv::Mat frame;
        *_video >> frame;

        if (frame.empty()) {
            _logger->Log(Logger::Level::Info, "TaskSplitVideo::Info Final frame complete.\n");
            return;
        }

        _spawn_cb(std::make_unique<TaskDetectCars>(std::make_shared<cv::Mat>(frame), std::to_string(frame_id)));

        frame_id++;
    }
}

void TaskSplitVideo::_Finish() {
    _logger->Log(Logger::Level::Info, "TaskSplitVideo::Info Finished splitting video.\n");
}
#include "splitVideo.h"

#include "core/tasks/yoloV7/detectCars.h"

TaskSplitVideo::TaskSplitVideo(std::filesystem::path video_path) {
    _video_path = video_path; 
}

void TaskSplitVideo::_Run() {
    cv::VideoCapture video(_video_path);

    if (!video.isOpened()) {
        _logger->Log(Logger::Level::Error, "TaskSplitVideo::Error Video not open.\n");
        return;
    }

    unsigned int frame_id = 0;
    while (!_flags.Get(Flags::Stop)) {
        cv::Mat frame;
        video >> frame;

        if (frame.empty()) {
            _logger->Log(Logger::Level::Info, "TaskSplitVideo::Info Final frame complete.\n");
            return;
        }

        _spawn_cb(std::make_unique<TaskDetectCars>(std::make_shared<cv::Mat>(frame), _video_path.filename(), frame_id));

        frame_id++;
    }
}

void TaskSplitVideo::_Finish() {
    _logger->Log(Logger::Level::Info, "TaskSplitVideo::Info Finished splitting video.\n");
}
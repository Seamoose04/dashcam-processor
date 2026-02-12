#include "yoloV7.h"

#include <darknet.hpp>

#include "core/tasks/yoloV7.h"

std::mutex YoloV7::_yolo_v7_mutex;

YoloV7::YoloV7() {}

void YoloV7::Load(Logger* logger) const {
    logger->Log(Logger::Level::Info, "Hardware::Info Loading yolov7...\n");
    std::scoped_lock<std::mutex> yolo_v7_lock(_yolo_v7_mutex);
    Darknet::set_output_stream(logger->GetFIFOPath());
    _yolo_v7 = std::make_unique<DarkHelp::NN>("models/yolov7/yolov7.cfg", "models/yolov7/yolov7.weights", "models/yolov7/coco.names");
}

void YoloV7::Process(std::shared_ptr<Task> task, Logger* logger, std::shared_ptr<TaskQueue> queue) const {
    std::shared_ptr<TaskYoloV7> task_yolo_v7 = std::static_pointer_cast<TaskYoloV7>(task);
    task_yolo_v7->Prepare(_yolo_v7.get());
    task_yolo_v7->Run(
        logger,
        [queue] (std::unique_ptr<Task> new_task) {
            queue->AddTask(std::move(new_task));
        }
    );
}

void YoloV7::Unload(Logger* logger) const {
    std::unique_lock<std::mutex> yolo_v7_lock(_yolo_v7_mutex);
    _yolo_v7.reset();
    yolo_v7_lock.unlock();
    logger->Log(Logger::Level::Info, "Hardware::Info Unloaded yolov7.\n");
}
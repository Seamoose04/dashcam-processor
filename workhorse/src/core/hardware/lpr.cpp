#include "lpr.h"

#include <darknet.hpp>

#include "core/tasks/lpr.h"

std::mutex LPR::_lpr_mutex;

LPR::LPR() {}

void LPR::Load(Logger* logger) const {
    logger->Log(Logger::Level::Info, "Hardware::Info Loading lpr...\n");
    std::scoped_lock<std::mutex> yolo_v7_lock(_lpr_mutex);
    Darknet::set_output_stream(logger->GetFIFOPath());
    _lpr = std::make_unique<DarkHelp::NN>("models/lpr/lpr.cfg", "models/lpr/backup/lpr_best.weights", "models/lpr/train/darknet_dataset/obj.names");
}

void LPR::Process(std::shared_ptr<Task> task, Logger* logger, std::shared_ptr<TaskQueue> queue) const {
    std::shared_ptr<TaskLPR> task_lpr = std::static_pointer_cast<TaskLPR>(task);
    task_lpr->Prepare(_lpr.get());
    task_lpr->Run(
        logger,
        [queue] (std::unique_ptr<Task> new_task) {
            queue->AddTask(std::move(new_task));
        }
    );
}

void LPR::Unload(Logger* logger) const {
    std::unique_lock<std::mutex> lpr_lock(_lpr_mutex);
    _lpr.reset();
    lpr_lock.unlock();
    logger->Log(Logger::Level::Info, "Hardware::Info Unloaded lpr.\n");
}

REGISTER_HARDWARE(LPR);
#pragma once

#include <DarkHelp.hpp>
#include <memory>

#include "core/hardware.h"

class YoloV7 : public Hardware {
public:
    YoloV7();

    void Load(Logger* logger) const override;
    void Process(std::shared_ptr<Task> task, Logger* logger, std::shared_ptr<TaskQueue> queue) const override;
    void Unload(Logger* logger) const override;

private:
    mutable std::unique_ptr<DarkHelp::NN> _yolo_v7;
    static std::mutex _yolo_v7_mutex;
};

REGISTER_HARDWARE(YoloV7);
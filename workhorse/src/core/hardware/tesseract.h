#pragma once

#include <tesseract/baseapi.h>
#include <memory>

#include "core/hardware.h"

class Tesseract : public Hardware {
public:
    Tesseract();

    void Load(Logger* logger) const override;
    void Process(std::shared_ptr<Task> task, Logger* logger, std::shared_ptr<TaskQueue> queue) const override;
    void Unload(Logger* logger) const override;

private:
    mutable std::unique_ptr<tesseract::TessBaseAPI> _tess;
    static std::mutex _tess_mutex;
};
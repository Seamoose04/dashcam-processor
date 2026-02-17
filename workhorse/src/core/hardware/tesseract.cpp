#include "tesseract.h"

#include <leptonica/allheaders.h>

#include "core/tasks/tesseract.h"

std::mutex Tesseract::_tess_mutex;

Tesseract::Tesseract() { }

void Tesseract::Load(Logger* logger) const {
    logger->Log(Logger::Level::Info, "Hardware::Info Loading tesseract...\n");
    std::scoped_lock<std::mutex> tesseract_lock(_tess_mutex);
    _tess = std::make_unique<tesseract::TessBaseAPI>();
    _tess->SetVariable("debug_file", logger->GetFIFOPath().c_str());
    _tess->Init(NULL, "eng");
}

void Tesseract::Process(std::shared_ptr<Task> task, Logger* logger, std::shared_ptr<TaskQueue> queue) const {
    std::shared_ptr<TaskTesseract> task_tess = std::static_pointer_cast<TaskTesseract>(task);
    task_tess->Prepare(_tess.get());
    task_tess->Run(
        logger,
        [queue] (std::unique_ptr<Task> new_task) {
            queue->AddTask(std::move(new_task));
        }
    );
}

void Tesseract::Unload(Logger* logger) const {
    std::unique_lock<std::mutex> tess_lock(_tess_mutex);
    _tess.reset();
    tess_lock.unlock();
    logger->Log(Logger::Level::Info, "Hardware::Info Unloaded tesseract.\n");
}

REGISTER_HARDWARE(Tesseract);
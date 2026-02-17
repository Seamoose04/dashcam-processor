#pragma once

#include <tesseract/baseapi.h>

#include "core/task.h"

class TaskTesseract : public Task {
public:
    TaskTesseract();
    void Prepare(tesseract::TessBaseAPI* tess);

protected:
    tesseract::TessBaseAPI* _tess;
};
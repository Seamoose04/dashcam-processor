#include "tesseract.h"

TaskTesseract::TaskTesseract() : Task("Tesseract") { }

void TaskTesseract::Prepare(tesseract::TessBaseAPI* tess) {
    _tess = tess;
}
#include "yoloV7.h"

TaskYoloV7::TaskYoloV7() : Task("YoloV7") { }

void TaskYoloV7::Prepare(DarkHelp::NN* nn) {
    _nn = nn;
}
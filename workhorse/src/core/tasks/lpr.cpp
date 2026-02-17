#include "lpr.h"

TaskLPR::TaskLPR() : Task("LPR") { }

void TaskLPR::Prepare(DarkHelp::NN* nn) {
    _nn = nn;
}
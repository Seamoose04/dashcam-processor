#pragma once

#include <DarkHelp.hpp>

#include "core/task.h"

class TaskYoloV7 : public Task {
public:
    TaskYoloV7();
    void Prepare(DarkHelp::NN* nn);

protected:
    DarkHelp::NN* _nn;
};
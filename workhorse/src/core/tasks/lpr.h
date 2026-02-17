#pragma once

#include <DarkHelp.hpp>

#include "core/task.h"

class TaskLPR : public Task {
public:
    TaskLPR();
    void Prepare(DarkHelp::NN* nn);

protected:
    DarkHelp::NN* _nn;
};
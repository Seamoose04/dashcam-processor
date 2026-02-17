#pragma once

#include <DarkHelp.hpp>
#include <memory>

#include "core/hardware.h"

class LPR : public Hardware {
public:
    LPR();

    void Load(Logger* logger) const override;
    void Process(std::shared_ptr<Task> task, Logger* logger, std::shared_ptr<TaskQueue> queue) const override;
    void Unload(Logger* logger) const override;

private:
    mutable std::unique_ptr<DarkHelp::NN> _lpr;
    static std::mutex _lpr_mutex;
};
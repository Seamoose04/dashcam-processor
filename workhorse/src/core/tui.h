#pragma once

#include <memory>
#include <ftxui/component/component.hpp>
#include <ftxui/component/screen_interactive.hpp>

#include "core/taskQueue.h"
#include "core/config.h"
#include "util/flag.h"
 
class Tui {
public:
    enum class Flags {
        Stop,
        Refreshing
    };
    Tui(Config config, std::shared_ptr<TaskQueue> queue);
    void Run();
    void Exit();
    
private:
    ftxui::Component GetComponent();
    
    Config _config;
    std::shared_ptr<TaskQueue> _queue;
    Flag<Flags> _flags;
    ftxui::ScreenInteractive _screen;
};

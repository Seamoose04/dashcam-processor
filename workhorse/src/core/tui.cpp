#include "tui.h"

#include <ftxui/dom/elements.hpp>

#include "util/timer.h"

Tui::Tui(Config config, std::shared_ptr<TaskQueue> queue) : _screen(ftxui::ScreenInteractive::Fullscreen()) {
    _config = config;
    _queue = queue;
}

ftxui::Component Tui::GetComponent() {
    return ftxui::Renderer([this]() -> ftxui::Element {
        std::unordered_map<std::string, unsigned int> tasks = _queue->GetTaskCounts();
        unsigned int in_progress = _queue->GetInProgressTasks();
        
        // Config with nice spacing
        auto config_grid = ftxui::gridbox({
            {ftxui::text("Workers: "), ftxui::text(std::to_string(_config.MAX_WORKERS)) | ftxui::bold},
            {ftxui::text("Log Level: "), ftxui::text(Logger::LevelToString(_config.LOG_LEVEL)) | ftxui::bold}
        });
        
        // Queue table with header row
        std::vector<std::vector<ftxui::Element>> queue_rows = {
            {ftxui::text("Task Type") | ftxui::bold | ftxui::center, ftxui::text("Count") | ftxui::bold | ftxui::center},
        };
        
        for (const auto& [task_type, count] : tasks) {
            queue_rows.push_back({
                ftxui::text(task_type),
                ftxui::text(std::to_string(count)) | ftxui::center
            });
        }
        queue_rows.push_back({
            ftxui::text("In Progress"),
            ftxui::text(std::to_string(in_progress)) | ftxui::center
        });
        
        auto queue_table = ftxui::gridbox(queue_rows);
        
        return ftxui::vbox({
            ftxui::window(ftxui::text(" Config "), config_grid | ftxui::border),
            ftxui::window(ftxui::text(" Task Queue "), queue_table | ftxui::border)
        }) | ftxui::border;
    });
}

void Tui::Run() {
    auto component = GetComponent();

    _queue->SubscribeChanges([this]() {
        if (_flags.Get(Flags::Refreshing)) {
            return;
        }
        _flags.Add(Flags::Refreshing);
        Timer timer(100, [this]() {
            _screen.Post(ftxui::Event::Custom);
            _flags.Clear(Flags::Refreshing);
        }, false);
    });

    component |= ftxui::CatchEvent([this] (ftxui::Event event) {
        if (event == ftxui::Event::Character('q')) {
            _flags.Add(Flags::Quit);
            _screen.Exit();
            return true;
        }
        
        if (event == ftxui::Event::Custom && _flags.Get(Flags::Stop)) {
            _screen.Exit();
            return true;
        }

        return false;
    });

    _screen.Loop(component);
}

void Tui::Stop() {
    _flags.Add(Flags::Stop);
    _screen.Post(ftxui::Event::Custom);
}

bool Tui::QuitRequested() {
    return _flags.Get(Flags::Quit);
}
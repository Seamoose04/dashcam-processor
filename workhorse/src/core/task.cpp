#include "task.h"

#include "core/hardware.h"

Task::Task(std::string type) : _type(type) { }

bool Task::operator==(const Task& other) const {
    return this == &other;
}

void Task::Run(Logger* logger, std::function<void(std::unique_ptr<Task>)> spawn_cb) {
    _logger = logger;
    _spawn_cb = spawn_cb;
    _Run();
    Finish();
}

void Task::Finish() {
    _Finish();
    _logger = nullptr;
}

std::string Task::GetType() {
    return _type;
}
#include "task.h"

Task::Task(Hardware type) : _type(type) { }

bool Task::operator==(const Task& other) const {
    return this == &other;
}

void Task::Start(Logger& logger) {
    _Start(logger);
}

void Task::Quit() {
    _flags.Add(Task::Flags::Quit);
}

void Task::Finish(Logger& logger) {
    _Finish(logger);
}
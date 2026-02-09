#include "task.h"

Task::Task(Hardware type) : _type(type) { }

bool Task::operator==(const Task& other) const {
    return this == &other;
}

void Task::Run(Logger& logger) {
    _Run(logger);
    Finish(logger);
}

void Task::Finish(Logger& logger) {
    _Finish(logger);
}

Hardware Task::GetType() {
    return _type;
}
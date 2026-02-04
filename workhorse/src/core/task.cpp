#include "task.h"

bool Task::operator==(const Task& other) const {
    return this == &other;
}

void Task::Start() {
    _Start();
}

void Task::Stop() {
    _flags.Add(Task::Flags::Quit);
}

void Task::Finish() {
    _Finish();
}
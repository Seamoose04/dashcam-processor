#include "task.h"

void Task::Start() {
    _Start();
}

void Task::Stop() {
    _flags.Add(Task::Flags::Quit);
}

void Task::Finish() {
    _Finish();
}
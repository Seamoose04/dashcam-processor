#include "worker.h"

Worker::Worker(Hardware type): _type(type) { }

void Worker::Work(std::shared_ptr<TaskQueue> queue) {
    _queue = std::move(queue);

    while (!(_flags.Get(Flags::Quit) || _flags.Get(Flags::Stop))) {
        _current_task = queue->GetNextTask(_type);
        _current_task->Start();
        _current_task->Run();
    }
}

void Worker::Stop() {
    _flags.Add(Flags::Stop);
}

void Worker::Quit() {
    _flags.Add(Flags::Quit);
    _current_task->Quit();
}
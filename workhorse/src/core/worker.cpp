#include "worker.h"

Worker::Worker(Hardware type, Logger::Config logger_conf)
    : _type(type), _logger(logger_conf) {}

void Worker::Work(std::shared_ptr<TaskQueue> queue) {
    _queue = std::move(queue);

    while (!_flags.Get(Flags::Stop)) {
        _flags.Add(Flags::Idle);
        _current_task = _queue->GetNextTask(
            _type, [this]() -> bool { return _flags.Get(Flags::Stop); });
        if (_current_task == nullptr) {
            break;
        }
        _flags.Clear(Flags::Idle);
        _current_task->Start(_logger);
        _current_task->Run(_logger);
        _queue->TaskFinished(_current_task);
    }
}

void Worker::Stop() {
    _flags.Add(Flags::Stop);
}

void Worker::Quit() {
    _flags.Add(Flags::Quit);
    _current_task->Quit();
}

bool Worker::GetIsIdle() {
    return _flags.Get(Flags::Idle);
}

#include "worker.h"

Worker::Worker(Hardware type, Logger::Config logger_conf)
    : _type(type), _logger(std::make_unique<Logger>(logger_conf)) {}

void Worker::Work(std::shared_ptr<TaskQueue> queue) {
    _queue = std::move(queue);

    while (!_flags.Get(Flags::Stop)) {
        _flags.Add(Flags::Idle);
        _current_task = _queue->GetNextTask(
            _type, 
            [this]() -> bool {
                return _flags.Get(Flags::Stop);
            }
        );
        if (_current_task == nullptr) {
            break;
        }
        _flags.Clear(Flags::Idle);
        _current_task->Run(
            _logger.get(),
            [this] (std::unique_ptr<Task> task) {
                _queue->AddTask(std::move(task));
            }
        );
        _queue->TaskFinished(_current_task);
    }
}

void Worker::Stop() {
    _flags.Add(Flags::Stop);
}

bool Worker::GetIsIdle() {
    return _flags.Get(Flags::Idle);
}

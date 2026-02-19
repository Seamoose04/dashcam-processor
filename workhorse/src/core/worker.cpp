#include "worker.h"

Worker::Worker(Logger::Config logger_conf)
    : _logger(std::make_unique<Logger>(logger_conf)) {}

void Worker::Work(std::shared_ptr<TaskQueue> queue) {
    _queue = std::move(queue);

    while (!_flags.Get(Flags::Stop)) {
        if (_type == nullptr) {
            _flags.Add(Flags::Idle);
            _signal.acquire();
        }

        _flags.Clear(Flags::Idle);
        _task = _queue->GetNextTask(_type->GetTypeName());
        if (_task == nullptr) {
            size_t subscription_id = _queue->SubscribeChanges([this]() { _signal.release(); }, _type->GetTypeName());
            _task = _queue->GetNextTask(_type->GetTypeName());
            if (_task == nullptr) {
                _flags.Add(Flags::Idle);
                _signal.acquire();
                _queue->UnsubscribeChanges(subscription_id);
                
                continue;
            } else {
                _queue->UnsubscribeChanges(subscription_id);
            }
        }

        _type->Process(_task, _logger.get(), _queue);
        _queue->TaskFinished(_task);
    }
}

void Worker::SetType(std::unique_ptr<Hardware> type) {
    if (_type != nullptr) {
        _type->Unload(_logger.get());
    }
    _type = std::move(type);
    _type->Load(_logger.get());
    _signal.release();
}

void Worker::Stop() {
    _flags.Add(Flags::Stop);
}

bool Worker::GetIsIdle() {
    return _flags.Get(Flags::Idle);
}

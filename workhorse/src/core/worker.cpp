#include "worker.h"

Worker::Worker(Logger::Config logger_conf)
    : _logger(std::make_unique<Logger>(logger_conf)) {}

void Worker::Work(std::shared_ptr<TaskQueue> queue) {
    _queue = std::move(queue);

    while (!_flags.Get(Flags::Stop)) {
		std::unique_lock type_lock(_type_mutex);
		_flags.Add(Flags::Idle);

		_cv.wait(type_lock, [this] {
			return _type != nullptr || _flags.Get(Flags::Stop);
		});

		if (_flags.Get(Flags::Stop)) {
			break;
		}

        _flags.Clear(Flags::Idle);
        _task = _queue->GetNextTask(_type->GetTypeName());

        if (_task == nullptr) {
			bool task_signalled = false;

            _pending_subscription = _queue->SubscribeChangesOnce([this, &task_signalled]() {
				std::scoped_lock lock (_type_mutex);
				_pending_subscription = 0;
				task_signalled = true;
				_cv.notify_one();
			}, _type->GetTypeName());

            _task = _queue->GetNextTask(_type->GetTypeName());
            if (_task == nullptr) {
                _flags.Add(Flags::Idle);
				_cv.wait(type_lock, [this, &task_signalled] {
					return task_signalled || _type == nullptr || _flags.Get(Flags::Stop);
				});

				if (_pending_subscription != 0) {
					_queue->UnsubscribeChanges(_pending_subscription);
					_pending_subscription = 0;
				}
                continue;
            }
        }

        _type->Process(_task, _logger.get(), _queue);
        _queue->TaskFinished(_task);
    }
	if (_pending_subscription != 0) {
		_queue->UnsubscribeChanges(_pending_subscription);
	}
}

void Worker::SetType(std::unique_ptr<Hardware> type) {
	std::scoped_lock type_lock(_type_mutex);
    if (_type != nullptr) {
        _type->Unload(_logger.get());
    }
    _type = std::move(type);
    _type->Load(_logger.get());
	_flags.Clear(Flags::Idle);
	if (_pending_subscription != 0) {
		_queue->UnsubscribeChanges(_pending_subscription);
		_pending_subscription = 0;
	}
	_cv.notify_one();
}

void Worker::Stop() {
    _flags.Add(Flags::Stop);
	_cv.notify_one();
}

bool Worker::GetIsIdle() {
    return _flags.Get(Flags::Idle);
}

const Hardware* Worker::GetType() const {
	return _type.get();
};

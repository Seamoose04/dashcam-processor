#include "worker.h"

Worker::Worker(std::vector<std::shared_ptr<Hardware>> types, Logger::Config logger_conf)
    : _types(std::move(types)), _logger(std::make_unique<Logger>(logger_conf)) {}

void Worker::Work(std::shared_ptr<TaskQueue> queue) {
    _queue = std::move(queue);

    auto current_type = &(*_types.begin());
    current_type->get()->Load(_logger.get());

    while (!_flags.Get(Flags::Stop)) {
        _flags.Add(Flags::Idle);

        std::unordered_map<std::string, unsigned int> task_counts = _queue->GetTaskCounts();
        if (task_counts[current_type->get()->GetTypeName()] == 0) {
            std::string new_type_name = current_type->get()->GetTypeName();
            for (auto& type : _types) {
                if (task_counts[type.get()->GetTypeName()] > task_counts[new_type_name]) {
                    new_type_name = type.get()->GetTypeName();
                }
            }

            if (current_type->get()->GetTypeName() != new_type_name) {
                for (auto& type : _types) {
                    if (type.get()->GetTypeName() == new_type_name) {
                        current_type->get()->Unload(_logger.get());
                        current_type = &type;
                        current_type->get()->Load(_logger.get());
                    }
                }
            }
        }

        _current_task = _queue->GetNextTask(
            current_type->get()->GetTypeName(), 
            [this]() -> bool {
                return _flags.Get(Flags::Stop);
            }
        );
        if (_current_task == nullptr) {
            break;
        }
        _flags.Clear(Flags::Idle);
        current_type->get()->Process(_current_task, _logger.get(), _queue);
        _queue->TaskFinished(_current_task);
    }
}

void Worker::Stop() {
    _flags.Add(Flags::Stop);
}

bool Worker::GetIsIdle() {
    return _flags.Get(Flags::Idle);
}

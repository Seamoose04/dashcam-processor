#include "taskQueue.h"

#include <utility>

TaskQueue::TaskQueue() {
    for (int i = 0; i < static_cast<int>(Hardware::Type::MAX_COUNT); i++) {
        _unclaimed_tasks.try_emplace(Hardware(static_cast<Hardware::Type>(i)));
    }
}

void TaskQueue::AddTask(std::unique_ptr<Task> task) {
    HardwareQueue& unclaimed_hardware_tasks = _unclaimed_tasks[task->GetType()];
    std::unique_lock<std::mutex> unclaimed_tasks_lock(unclaimed_hardware_tasks.mutex);
    unclaimed_hardware_tasks.tasks.push(std::move(task));
    unclaimed_tasks_lock.unlock();
    
    unclaimed_hardware_tasks.are_tasks_available.notify_one();
}

std::shared_ptr<Task> TaskQueue::GetNextTask(Hardware type, std::function<bool()> stop_condition) {
    HardwareQueue& unclaimed_hardware_tasks = _unclaimed_tasks[type];
    std::unique_lock<std::mutex> unclaimed_tasks_lock(unclaimed_hardware_tasks.mutex);

    unclaimed_hardware_tasks.are_tasks_available.wait(unclaimed_tasks_lock, [&]() {
        return !unclaimed_hardware_tasks.tasks.empty() || stop_condition();
    });

    if (stop_condition()) {
        return nullptr;
    }
    
    std::shared_ptr<Task> task = std::move(unclaimed_hardware_tasks.tasks.front());
    unclaimed_hardware_tasks.tasks.pop();
    unclaimed_tasks_lock.unlock();

    Task* task_ptr = task.get();

    std::unique_lock<std::mutex> unfinished_tasks_lock(_unfinished_tasks_mutex);
    _unfinished_tasks.insert(task);
    unfinished_tasks_lock.unlock();

    return task;
}

void TaskQueue::TaskFinished(std::shared_ptr<Task> task) {
    std::unique_lock<std::mutex> unfinished_tasks_lock(_unfinished_tasks_mutex);
    _unfinished_tasks.erase(task);
    unfinished_tasks_lock.unlock();
}

void TaskQueue::NotifyAll() {
    for (unsigned int i = 0; i < static_cast<unsigned int>(Hardware::Type::MAX_COUNT); i++) {
        HardwareQueue& unclaimed_hardware_tasks = _unclaimed_tasks[static_cast<Hardware::Type>(i)];
        unclaimed_hardware_tasks.are_tasks_available.notify_all();
    }
}

unsigned int TaskQueue::GetInProgressTasks() {
    std::scoped_lock<std::mutex> unfinished_tasks_lock(_unfinished_tasks_mutex);
    unsigned int tasks_in_progress = _unfinished_tasks.size();
    return tasks_in_progress;
}

unsigned int TaskQueue::GetUnclaimedTasks() {
    unsigned int unclaimed_tasks = 0;
    for (unsigned int i = 0; i < static_cast<unsigned int>(Hardware::Type::MAX_COUNT); i++) {
        HardwareQueue& queue = _unclaimed_tasks[static_cast<Hardware::Type>(i)];
        std::scoped_lock<std::mutex> unclaimed_tasks_lock(_unfinished_tasks_mutex);
        unclaimed_tasks += queue.tasks.size();
    }
    return unclaimed_tasks;
}
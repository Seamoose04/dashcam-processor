#include "taskQueue.h"

#include <utility>

#include "util/registry.h"

TaskQueue::TaskQueue() {
    auto types = Registry<Hardware>::Instance().GetRegisteredTypes();
    for (std::string type : types) {
        _unclaimed_tasks.try_emplace(type);
    }
}

void TaskQueue::AddTask(std::unique_ptr<Task> task) {
    HardwareQueue& unclaimed_hardware_tasks = _unclaimed_tasks[task->GetType()];
    std::unique_lock<std::mutex> unclaimed_tasks_lock(unclaimed_hardware_tasks.mutex);
    unclaimed_hardware_tasks.tasks.push(std::move(task));
    unclaimed_tasks_lock.unlock();
    
    unclaimed_hardware_tasks.are_tasks_available.notify_one();
}

std::shared_ptr<Task> TaskQueue::GetNextTask(std::string type, std::function<bool()> stop_condition) {
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
    auto types = Registry<Hardware>::Instance().GetRegisteredTypes();
    for (auto& type : types) {
        HardwareQueue& unclaimed_hardware_tasks = _unclaimed_tasks[type];
        unclaimed_hardware_tasks.are_tasks_available.notify_all();
    }
}

std::unordered_map<std::string, unsigned int> TaskQueue::GetTaskCounts() {
    std::unordered_map<std::string, unsigned int> counts;
    auto types = Registry<Hardware>::Instance().GetRegisteredTypes();
    for (auto& type : types) {
        counts.try_emplace(type);
        HardwareQueue& queue = _unclaimed_tasks[type];
        std::scoped_lock<std::mutex> unclaimed_tasks_lock(queue.mutex);
        counts[type] = queue.tasks.size();
    }
    return counts;
}

unsigned int TaskQueue::GetInProgressTasks() {
    std::scoped_lock<std::mutex> unfinished_tasks_lock(_unfinished_tasks_mutex);
    unsigned int tasks_in_progress = _unfinished_tasks.size();
    return tasks_in_progress;
}

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
    unclaimed_hardware_tasks.callbacks.Call();
    unclaimed_tasks_lock.unlock();
    
    _callbacks.Call();
}

std::shared_ptr<Task> TaskQueue::GetNextTask(std::string type) {
    HardwareQueue& unclaimed_hardware_tasks = _unclaimed_tasks[type];
    std::unique_lock<std::mutex> unclaimed_tasks_lock(unclaimed_hardware_tasks.mutex);

    if (unclaimed_hardware_tasks.tasks.size() == 0) {
        unclaimed_tasks_lock.unlock();
        return nullptr;
    }
    
    std::shared_ptr<Task> task = std::move(unclaimed_hardware_tasks.tasks.front());
    unclaimed_hardware_tasks.tasks.pop();
    unclaimed_tasks_lock.unlock();

    Task* task_ptr = task.get();

    std::unique_lock<std::mutex> unfinished_tasks_lock(_unfinished_tasks_mutex);
    _unfinished_tasks.insert(task);
    unfinished_tasks_lock.unlock();

    _callbacks.Call();

    return task;
}

void TaskQueue::TaskFinished(std::shared_ptr<Task> task) {
    std::unique_lock<std::mutex> unfinished_tasks_lock(_unfinished_tasks_mutex);
    _unfinished_tasks.erase(task);
    unfinished_tasks_lock.unlock();
    _callbacks.Call();
}

// void TaskQueue::NotifyAll() {
//     auto types = Registry<Hardware>::Instance().GetRegisteredTypes();
//     for (auto& type : types) {
//         HardwareQueue& unclaimed_hardware_tasks = _unclaimed_tasks[type];
//         unclaimed_hardware_tasks.are_tasks_available.notify_all();
//     }
// }

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

size_t TaskQueue::SubscribeChanges(std::function<void()> callback) {
    return _callbacks.Subscribe(std::move(callback));
}

void TaskQueue::UnsubscribeChanges(size_t id) {
    _callbacks.Unsubscribe(id);
}

size_t TaskQueue::SubscribeChanges(std::function<void()> callback, std::string type) {
    HardwareQueue& unclaimed_hardware_tasks = _unclaimed_tasks[type];
    return unclaimed_hardware_tasks.callbacks.Subscribe(callback);
}

void TaskQueue::UnsubscribeChanges(size_t id, std::string type) {
    HardwareQueue& unclaimed_hardware_tasks = _unclaimed_tasks[type];
    unclaimed_hardware_tasks.callbacks.Unsubscribe(id);
}
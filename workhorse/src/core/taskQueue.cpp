#include "taskQueue.h"

#include <utility>

TaskQueue::TaskQueue() { }

void TaskQueue::AddTask(Hardware type, std::unique_ptr<Task> task) {
    HardwareQueue& unclaimed_hardware_tasks = _unclaimed_tasks[type];
    std::unique_lock<std::mutex> unclaimed_tasks_lock(unclaimed_hardware_tasks.mutex);
    unclaimed_hardware_tasks.tasks.push(std::move(task));
    unclaimed_tasks_lock.unlock();
    
    unclaimed_hardware_tasks.are_tasks_available.notify_one();
}

std::shared_ptr<Task> TaskQueue::GetNextTask(Hardware type) {
    HardwareQueue& unclaimed_hardware_tasks = _unclaimed_tasks[type];
    std::unique_lock<std::mutex> unclaimed_tasks_lock(unclaimed_hardware_tasks.mutex);

    unclaimed_hardware_tasks.are_tasks_available.wait(unclaimed_tasks_lock, [&]() {
        return !unclaimed_hardware_tasks.tasks.empty();
    });
    
    std::unique_ptr<Task> task = std::move(unclaimed_hardware_tasks.tasks.front());
    unclaimed_hardware_tasks.tasks.pop();
    unclaimed_tasks_lock.unlock();

    Task* task_ptr = task.get();

    std::unique_lock<std::mutex> unfinished_tasks_lock(_unfinished_tasks_mutex);
    _unfinished_tasks.insert(std::move(task));
    unfinished_tasks_lock.unlock();

    return std::move(task);
}

void TaskQueue::TaskFinished(std::shared_ptr<Task> task) {
    std::unique_lock<std::mutex> unfinished_tasks_lock(_unfinished_tasks_mutex);
    _unfinished_tasks.erase(task);
    unfinished_tasks_lock.unlock();
}
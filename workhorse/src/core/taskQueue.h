#pragma once

#include <queue>
#include <unordered_map>
#include <mutex>
#include <condition_variable>
#include <memory>

#include <core/task.h>
#include <core/hardware.h>

struct HardwareQueue {
    std::queue<std::unique_ptr<Task>> tasks;
    std::mutex mutex;
    std::condition_variable are_tasks_available;
};

class TaskQueue {
public:
    TaskQueue();
    void AddTask(Hardware type, std::unique_ptr<Task> task);
    std::shared_ptr<Task> GetNextTask(Hardware type);
    void TaskFinished(std::shared_ptr<Task> task);

private:
    std::unordered_map<Hardware, HardwareQueue> _unclaimed_tasks;
    std::unordered_set<std::shared_ptr<Task>> _unfinished_tasks;
    std::mutex _unfinished_tasks_mutex;
};
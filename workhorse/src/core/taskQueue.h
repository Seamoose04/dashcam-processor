#pragma once

#include <queue>
#include <unordered_map>
#include <mutex>
#include <condition_variable>
#include <memory>
#include <functional>

#include "core/task.h"

struct HardwareQueue {
    std::queue<std::unique_ptr<Task>> tasks = {};
    std::mutex mutex;
    std::condition_variable are_tasks_available;
};

class TaskQueue {
public:
    TaskQueue();
    void AddTask(std::unique_ptr<Task> task);
    std::shared_ptr<Task> GetNextTask(std::string type, std::function<bool()> stop_condition);
    void TaskFinished(std::shared_ptr<Task> task);
    
    void NotifyAll();
    
    std::unordered_map<std::string, unsigned int> GetTaskCounts();
    unsigned int GetInProgressTasks();
    
private:
    std::unordered_map<std::string, HardwareQueue> _unclaimed_tasks;
    std::unordered_set<std::shared_ptr<Task>> _unfinished_tasks;
    std::mutex _unfinished_tasks_mutex;
};
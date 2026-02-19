#pragma once

#include <queue>
#include <unordered_map>
#include <mutex>
#include <memory>
#include <functional>

#include "core/task.h"
#include "util/callback.h"

struct HardwareQueue {
    std::queue<std::unique_ptr<Task>> tasks = {};
    std::mutex mutex;
    Callback callbacks;
};

class TaskQueue {
public:
    TaskQueue();
    void AddTask(std::unique_ptr<Task> task);
    std::shared_ptr<Task> GetNextTask(std::string type);
    void TaskFinished(std::shared_ptr<Task> task);
    
    // void NotifyAll();
    
    std::unordered_map<std::string, unsigned int> GetTaskCounts();
    unsigned int GetInProgressTasks();
    size_t SubscribeChanges(std::function<void()> callback);
    void UnsubscribeChanges(size_t id);
    size_t SubscribeChanges(std::function<void()> callback, std::string type);
    void UnsubscribeChanges(size_t id, std::string type);
    
private:
    std::unordered_map<std::string, HardwareQueue> _unclaimed_tasks;
    std::unordered_set<std::shared_ptr<Task>> _unfinished_tasks;
    std::mutex _unfinished_tasks_mutex;
    Callback _callbacks;
};
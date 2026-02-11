#pragma once

#include <unordered_set>
#include <functional>
#include <memory>
#include <string>

#include "core/logger.h"
#include "util/flag.h"

class Hardware;

class Task {
public:
    Task(std::string type);
    bool operator==(const Task& other) const;

    void Run(Logger* logger, std::function<void(std::unique_ptr<Task>)> spawn_cb);
    void Finish();

    std::string GetType();

protected:
    virtual void _Run() = 0;
    virtual void _Finish() = 0;
    
    Logger* _logger;
    std::function<void(std::unique_ptr<Task>)> _spawn_cb;

private:
    std::string _type;
};
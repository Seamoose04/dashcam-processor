#pragma once

#include <unordered_map>
#include <functional>
#include <mutex>

class Callback {
public:
    Callback();
    size_t Subscribe(std::function<void()> callback);
    void Unsubscribe(size_t id);
    void Call();

private:
    std::unordered_map<int, std::function<void()>> _callbacks;
    std::mutex _mutex;
    size_t _next_id = 0;
};
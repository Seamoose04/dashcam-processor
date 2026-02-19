#include "callback.h"

Callback::Callback() { }

size_t Callback::Subscribe(std::function<void()> callback) {
    std::scoped_lock<std::mutex> lock(_mutex);
    size_t id = _next_id++;
    _callbacks[id] = std::move(callback);
    return id;
}

void Callback::Call() {
    std::scoped_lock<std::mutex> lock(_mutex);
    for (auto& callback : _callbacks) {
        callback.second();
    }
}

void Callback::Unsubscribe(size_t id) {
    std::scoped_lock<std::mutex> lock(_mutex);
    _callbacks.erase(id);
}
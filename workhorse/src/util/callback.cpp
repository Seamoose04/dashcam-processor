#include "callback.h"
#include <memory>

Callback::Callback() { }

size_t Callback::Subscribe(std::function<void()> callback) {
    std::scoped_lock<std::mutex> lock(_mutex);
    size_t id = _next_id++;
    _callbacks[id] = std::move(callback);
    return id;
}

size_t Callback::SubscribeOnce(std::function<void()> callback) {
	auto id = std::make_shared<size_t>(0);
	*id = Subscribe([this, callback, id]() {
		Unsubscribe(*id);
		callback();
	});
	return *id;
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

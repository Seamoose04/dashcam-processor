#include "timer.h"

#include <thread>
#include <chrono>

Timer::Timer(unsigned int millis, std::function<void()> callback, bool loop) {
    std::thread([millis, callback]() {
        std::this_thread::sleep_for(std::chrono::milliseconds(millis));
        callback();
    }).detach();
}
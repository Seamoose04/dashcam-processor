#pragma once

#include <functional>

class Timer {
public:
    Timer(unsigned int millis, std::function<void()>, bool loop);
};
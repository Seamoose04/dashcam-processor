#pragma once

template<typename T>
class Flag {
public:
    Flag() = default;

    void Set(T flag) {
        _states |= 2 ^ static_cast<unsigned int>(flag);
    }

private:
    T _flags;
    unsigned long _states;
};
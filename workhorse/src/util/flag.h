#pragma once

#include <type_traits>
#include <atomic>

template<typename Enum>
class Flag {
    static_assert(std::is_enum_v<Enum>, "Flag requires an enum type.");
public:
    Flag() = default;

    void Add(Enum flag) {
        _states.fetch_or(1ULL << static_cast<unsigned int>(flag), std::memory_order_release);
    }
    void Clear(Enum flag) {
        _states.fetch_and(~(1ULL << static_cast<unsigned int>(flag)), std::memory_order_release);
    }
    void Toggle(Enum flag) {
        _states.fetch_xor(1ULL << static_cast<unsigned int>(flag), std::memory_order_release);
    }
    void Set(Enum flag, bool state) {
        if (state) {
            Add(flag);
        } else {
            Clear(flag);
        }
    }
    bool Get(Enum flag) {
        return _states.load(std::memory_order_acquire) & (1ULL << static_cast<unsigned int>(flag));
    }

private:
    std::atomic<unsigned long long> _states{0};
};
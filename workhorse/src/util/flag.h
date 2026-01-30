#pragma once

#include <type_traits>

template<typename Enum>
class Flag {
    static_assert(std::is_enum_v<Enum>, "Flag requires an enum type.");
public:
    Flag() = default;

    void Add(Enum flag) {
        _states |= 1 << static_cast<unsigned int>(flag);
    }
    void Clear(Enum flag) {
        _states &= !(1 << static_cast<unsigned int>(flag));
    }
    void Toggle(Enum flag) {
        _states ^= 1 << static_cast<unsigned int>(flag);
    }
    void Set(Enum flag, bool state) {
        Clear(flag);
        _states |= 1 << static_cast<unsigned int>(flag);
    }
    bool Get(Enum flag) {
        return _states & (1 << static_cast<unsigned int>(flag));
    }

private:
    unsigned long long _states;
};
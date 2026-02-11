#pragma once

#include <functional>
#include <memory>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <iostream>

template<typename BaseType>
class Registry {
public:
    using Creator = std::function<std::shared_ptr<BaseType>()>;

    static Registry& Instance() {
        static Registry inst;
        return inst;
    }

    bool Register(const std::string& name, Creator creator) {
        auto [it, inserted] = _creators.emplace(name, std::move(creator));
        return inserted;
    }

    std::shared_ptr<BaseType> Create(const std::string& name) const {
        auto it = _creators.find(name);
        if (it != _creators.end()){
            auto instance = (it->second)();
            instance->SetTypeName(name);
            return instance;
        }  
        return nullptr;
    }

    std::unordered_set<std::string> GetRegisteredTypes() const {
        std::unordered_set<std::string> types;
        types.reserve(_creators.size());
        for (const auto& [name, creator] : _creators) {
            types.emplace(name);
        }
        return types;
    }

private:
    std::unordered_map<std::string, Creator> _creators;
};

// Generic (by class name)
#define REGISTER_TYPE(BaseType, DerivedType)                                \
    namespace {                                                             \
        struct DerivedType##__AutoRegistrar {                               \
            DerivedType##__AutoRegistrar() {                                \
                (void)Registry<BaseType>::Instance().Register(              \
                    #DerivedType,                                           \
                    [] { return std::make_shared<DerivedType>(); }          \
                );                                                          \
            }                                                               \
        };                                                                  \
        static const DerivedType##__AutoRegistrar global_##DerivedType##_registrar; \
    }

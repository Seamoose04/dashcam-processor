#include "cpu.h"

#include "core/tasks/cpu.h"

CPU::CPU() {}

void CPU::Process(std::shared_ptr<Task> task, Logger* logger, std::shared_ptr<TaskQueue> queue) const {
    std::shared_ptr<TaskCPU> task_cpu = std::static_pointer_cast<TaskCPU>(task);
    task_cpu->Run(
        logger,
        [queue] (std::unique_ptr<Task> new_task) {
            queue->AddTask(std::move(new_task));
        }
    );
}

REGISTER_HARDWARE(CPU)
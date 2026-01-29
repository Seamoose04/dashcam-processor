#include "testCPU.h"

#include <iostream>

void TaskTestCPU::Prepare() {
    std::cout << "starting" << std::endl;
}

void TaskTestCPU::Run() {
    for (int i = 0; i <= 100000; i++) {
        if (i % 10000 == 0) {
            std::cout << "Running. Progress: " << i / 10000 << "/10" << std::endl;
        }
    }
    Finish();
}

void TaskTestCPU::Finish() {
    std::cout << "finished" << std::endl;
}

void TaskTestCPU::Stop(bool immediate) {
    std::cout << "stopping. immediately?: " << immediate << std::endl;
}
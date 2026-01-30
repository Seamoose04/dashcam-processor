#include "testCPU.h"

#include <iostream>

void TaskTestCPU::_Start() {
    std::cout << "starting" << std::endl;
}

void TaskTestCPU::Run() {
    for (int i = 0; i <= 100000; i++) {
        if (_flags.Get(Flags::Quit)) {
            std::cout << "Stopped early" << std::endl;
            return;
        }
        if (i % 10000 == 0) {
            std::cout << "Running. Progress: " << i / 10000 << "/10" << std::endl;
        }
    }
    Finish();
}

void TaskTestCPU::_Finish() {
    std::cout << "finished" << std::endl;
}
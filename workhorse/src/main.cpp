#include <cstdlib>
#include "core/tasks/testCPU.h"

int main() {
    TaskTestCPU task;
    task.Prepare();
    task.Run();
    task.Stop();
    return EXIT_SUCCESS;
}
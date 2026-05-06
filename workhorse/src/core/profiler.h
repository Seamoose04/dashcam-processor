#pragma once

#include <nvml.h>

#include "core/hardware.h"
#include "core/logger.h"
#include "core/resources.h"

class Profiler {
public:
	void Init(Logger* logger);
	Resources Profile(Hardware* hardware);
	~Profiler();

private:
	nvmlDevice_t _device;
	Logger* _logger;
};

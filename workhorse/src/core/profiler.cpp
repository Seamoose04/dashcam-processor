#include "profiler.h"

#include <format>

void Profiler::Init(Logger* logger) {
	_logger = logger;
	nvmlInit();
	nvmlDeviceGetHandleByIndex(0, &_device);
}

Resources Profiler::Profile(Hardware* hardware) {
	nvmlMemory_t mem_start;
	nvmlDeviceGetMemoryInfo(_device, &mem_start);

	auto load_start = std::chrono::steady_clock::now();
	hardware->Load(_logger);
	auto load_end = std::chrono::steady_clock::now();

	nvmlMemory_t mem_load;
	nvmlDeviceGetMemoryInfo(_device, &mem_load);

	auto unload_start = std::chrono::steady_clock::now();
	hardware->Unload(_logger);
	auto unload_end = std::chrono::steady_clock::now();

	nvmlMemory_t mem_end;
	nvmlDeviceGetMemoryInfo(_device, &mem_end);

	Resources resources;
	long long vram_delta_raw = mem_load.free - mem_end.free + mem_load.free - mem_start.free;

	resources.vram = vram_delta_raw < 0 ? 0.0f : static_cast<float>(vram_delta_raw) / 2.0f / (1024.0f * 1024.0f * 1024.0f);
	resources.load_ms = std::chrono::duration_cast<std::chrono::milliseconds>(load_end - load_start).count();
	resources.unload_ms = std::chrono::duration_cast<std::chrono::milliseconds>(unload_end - unload_start).count();

	_logger->Log(Logger::Level::Info, std::format("Hardware: {}, load_ms: {}, vram: {}, unload_ms: {}\n",
				hardware->GetTypeName(), resources.load_ms, resources.vram, resources.unload_ms));

	return resources;
}

Profiler::~Profiler() {
	nvmlShutdown();	
}

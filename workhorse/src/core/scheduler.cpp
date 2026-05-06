#include "scheduler.h"

#include <format>
#include "core/profiler.h"

Scheduler::Scheduler(Config conf, Logger::Config worker_log_conf, Logger::Config log_conf) : _logger(log_conf) {
    _workers.reserve(conf.MAX_WORKERS);
	_available_vram = conf.AVAILABLE_VRAM;

    for (unsigned int i = 0; i < conf.MAX_WORKERS; i++) {
        Logger::Config current_worker_log_conf = worker_log_conf;
        current_worker_log_conf.path /= std::format("worker{}.txt", i);
        _workers.push_back(std::make_unique<Worker>(current_worker_log_conf));
    }
}

void Scheduler::Run(std::shared_ptr<TaskQueue> task_queue) {
	Profiler profiler;
	profiler.Init(&_logger);

	auto type_names = Registry<Hardware>::Instance().GetRegisteredTypes();
	for (const auto& type_name : type_names) {
		auto hardware = Registry<Hardware>::Instance().Create(type_name);
		_resources[hardware->GetTypeName()] = profiler.Profile(hardware.get());
	}

    std::shared_ptr<TaskQueue> tasks = std::move(task_queue);
    _worker_threads.reserve(_workers.size());
    for (auto& worker : _workers) {
        _worker_threads.emplace_back(&Worker::Work, worker.get(), tasks);
    }

    while (!_quit) {
		std::unordered_map<std::string, unsigned int> counts = tasks->GetTaskCounts();
		unsigned int total = 0;
		unsigned int max_count = 0;
		std::string max_task;
		for (auto& count : counts) {
			if (count.second > 0) {
				total += count.second;
				if (count.second > max_count) {
					max_count = count.second;
					max_task = count.first;
				}
			}
		}

		if (total == 0) {
			if (tasks->GetInProgressTasks() == 0) {
				break;
			}
			std::this_thread::sleep_for(std::chrono::milliseconds(100));
			continue;
		}
		
		std::vector<Worker*> idle_workers;
		for (auto& worker : _workers) {
			if (worker->GetIsIdle()) {
				idle_workers.push_back(worker.get());
			}
		}
		if (idle_workers.size() == 0) {
			std::this_thread::sleep_for(std::chrono::milliseconds(100));
			continue;
		}

		Resources needed_resources = _resources[max_task];
		std::erase_if(idle_workers, [&](Worker* w) {
			const auto* type = w->GetType();
			float vram_if_freed = type == nullptr ? 0.0f : _resources[type->GetTypeName()].vram;
			return (_available_vram - needed_resources.vram + vram_if_freed) < 0.0f;
		});
		if (idle_workers.size() == 0) {
			std::this_thread::sleep_for(std::chrono::milliseconds(100));
			continue;
		}

		std::stable_sort(idle_workers.begin(), idle_workers.end(), [&](Worker* a, Worker* b) {
			const auto* type_a = a->GetType();
			const auto* type_b = b->GetType();

			float unload_a = type_a != nullptr ? _resources[type_a->GetTypeName()].unload_ms : 0;
			float unload_b = type_b != nullptr ? _resources[type_b->GetTypeName()].unload_ms : 0;

			if (unload_a != unload_b) {
				return unload_a < unload_b;
			}

			float vram_a = type_a != nullptr ? _resources[type_a->GetTypeName()].vram : 0;
			float vram_b = type_b != nullptr ? _resources[type_b->GetTypeName()].vram : 0;
			if (vram_a != vram_b) {
				return vram_a > vram_b;
			}

			return false;
		});

		std::unique_ptr<Hardware> new_hardware = Registry<Hardware>::Instance().Create(max_task);
		idle_workers[0]->SetType(std::move(new_hardware));
    }
	
	_Complete();
}

void Scheduler::Stop() {
	_quit = true;
    for (auto& worker : _workers) {
        worker->Stop();
    }
    for (auto& worker_thread : _worker_threads) {
        if (worker_thread.joinable()) {
            worker_thread.join();
        }
    }
}

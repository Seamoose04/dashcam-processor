#pragma once

#include <atomic>

#include "callback.h"

class Service {
public:
	virtual ~Service() = default;
	bool StopRequested() const;

	Callback onComplete;

protected:
	void _Complete();

	std::atomic<bool> _stop{false};
};

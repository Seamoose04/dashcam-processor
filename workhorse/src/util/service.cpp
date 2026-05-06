#include "service.h"

bool Service::StopRequested() const {
	return _stop;
}

void Service::_Complete() {
	_stop = true;
	onComplete.Call();
}

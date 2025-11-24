# pipeline/shutdown.py
from threading import Event as ThreadEvent
from multiprocessing import Event as ProcessEvent

# Stop producing new work (VideoReaders, dispatchers stop scheduling)
stop = ThreadEvent()

# After queues drain: tell workers in other processes to exit loops and terminate
terminate = ProcessEvent()

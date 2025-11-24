# pipeline/shutdown.py
from threading import Event

# Stop producing new work (VideoReaders, dispatchers stop scheduling)
stop = Event()

# After queues drain: tell workers to exit loops and terminate
terminate = Event()
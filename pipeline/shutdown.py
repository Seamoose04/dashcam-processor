# pipeline/shutdown.py
from threading import Event

shutdown_event = Event()

def request_shutdown():
    shutdown_event.set()

def is_shutdown():
    return shutdown_event.is_set()
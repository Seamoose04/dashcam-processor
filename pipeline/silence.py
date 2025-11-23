# pipeline/utils/yolo_silence.py
import os
import sys
import io
import logging
from contextlib import contextmanager

def silence_ultralytics():
    """
    Globally silence ultralytics logging AND stdout spam.
    Call this BEFORE loading YOLO models.
    """
    # 1) Disable ultralytics logging
    os.environ["ULTRALYTICS_LOGGING"] = "false"

    # 2) Mutate ultralytics loggers
    try:
        import ultralytics
        import logging
        log = logging.getLogger("ultralytics")
        log.handlers.clear()
        log.propagate = False
        log.setLevel(logging.ERROR)
    except Exception:
        pass

@contextmanager
def suppress_stdout():
    """
    Context manager that suppresses ALL stdout prints.
    """
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        yield
    finally:
        sys.stdout = old_stdout

# pipeline/logger.py
import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = "logs"

def get_logger(name: str):
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # already created

    logger.setLevel(logging.INFO)

    handler = RotatingFileHandler(
        os.path.join(LOG_DIR, f"{name}.log"),
        maxBytes=5_000_000,
        backupCount=5
    )
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(processName)s] %(message)s",
        "%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.propagate = False
    return logger

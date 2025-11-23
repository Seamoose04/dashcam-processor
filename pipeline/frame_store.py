# pipeline/frame_store.py
from __future__ import annotations

import os
from typing import Optional

import numpy as np

from pipeline.logger import get_logger
log = get_logger("framestore")

_BASE_DIR: Optional[str] = None

def init(base_dir: str = "frame_store") -> None:
    """Initialize the frame store base directory."""
    global _BASE_DIR
    _BASE_DIR = base_dir
    os.makedirs(_BASE_DIR, exist_ok=True)


def _ensure_init() -> None:
    if _BASE_DIR is None:
        init()  # default


def _frame_path(video_id: str, frame_idx: int) -> str:
    _ensure_init()
    assert _BASE_DIR is not None
    vdir = os.path.join(_BASE_DIR, str(video_id))
    os.makedirs(vdir, exist_ok=True)
    return os.path.join(vdir, f"{frame_idx}.npy")


def save_frame(video_id: str, frame_idx: int, frame: np.ndarray) -> str:
    """
    Save a frame to disk and return a payload_ref string like 'video:123'.
    """
    try:
        path = _frame_path(video_id, frame_idx)
        np.save(path, frame)
    except Exception as e:
        log.exception(f"Failed to save frame {video_id}:{frame_idx}: {e}")
    return f"{video_id}:{frame_idx}"


def load_frame(payload_ref: str) -> np.ndarray:
    """
    Load a frame from disk using a payload_ref like 'video:123'.
    """
    try:
        _ensure_init()
        video_id, frame_idx_str = str(payload_ref).split(":")
        frame_idx = int(frame_idx_str)
        path = _frame_path(video_id, frame_idx)
        return np.load(path)
    except Exception as e:
        log.exception(f"Failed to load frame {payload_ref}: {e}")
        raise

def delete_frame(payload_ref: str):
    video_id, frame_idx_str = payload_ref.split(":")
    frame_idx = int(frame_idx_str)

    path = _frame_path(video_id, frame_idx)
    if os.path.exists(path):
        os.remove(path)

    folder = os.path.dirname(path)
    if os.path.exists(folder) and not os.listdir(folder):
        os.rmdir(folder)

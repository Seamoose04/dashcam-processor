# pipeline/frame_store.py
from __future__ import annotations

import os
from typing import Optional, Iterable
from multiprocessing import Lock as MpLock

import numpy as np

from pipeline.logger import get_logger
log = get_logger("framestore")

_BASE_DIR: Optional[str] = None
_refcounts = None  # Manager().dict expected
_lock: Optional[MpLock] = None

def init(base_dir: str = "frame_store", refcounts=None, lock: Optional[MpLock] = None) -> None:
    """Initialize the frame store base directory and shared refcounts."""
    global _BASE_DIR, _refcounts, _lock
    _BASE_DIR = base_dir
    _refcounts = refcounts
    _lock = lock
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


def add_refs(refs: Iterable[str]) -> None:
    """Increment reference counts for payload refs (shared across processes)."""
    if _refcounts is None or _lock is None:
        return
    with _lock:
        for ref in refs:
            if ref is None:
                continue
            current = _refcounts.get(ref, 0)
            _refcounts[ref] = current + 1
            log.info("[FrameStore] add_ref %s -> %s", ref, _refcounts[ref])


def release_refs(refs: Iterable[str]) -> None:
    """Decrement reference counts; delete frames whose count reaches zero."""
    if _refcounts is None or _lock is None:
        return
    to_delete = []
    with _lock:
        for ref in refs:
            if ref is None:
                continue
            current = _refcounts.get(ref, 0)
            if current <= 1:
                _refcounts.pop(ref, None)
                to_delete.append(ref)
            else:
                _refcounts[ref] = current - 1
            log.info("[FrameStore] release_ref %s -> %s", ref, _refcounts.get(ref, 0))

    for ref in to_delete:
        try:
            delete_frame(ref)
            log.info("[FrameStore] Deleted %s (refcount=0)", ref)
        except Exception as e:
            log.exception(f"[FrameStore] Failed to delete {ref}: {e}")

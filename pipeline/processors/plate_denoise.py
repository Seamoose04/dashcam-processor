# pipeline/processors/plate_denoise.py
from __future__ import annotations

import os
import cv2
import numpy as np

from pipeline import frame_store
from pipeline.task import Task

# Optional debug hook: set PLATE_DENOISE_DEBUG_SAVE=/path/to/output.png to save
# the first denoised plate ROI to disk for manual inspection.
DEBUG_SAVE_PATH = os.environ.get("PLATE_DENOISE_DEBUG_SAVE")
_debug_saved = False

# Tunables (env overrides) to help with faint/blurred characters.
_H = float(os.environ.get("PLATE_DENOISE_H", 8))
_HCOLOR = float(os.environ.get("PLATE_DENOISE_HCOLOR", 8))
_DO_ENHANCE = os.environ.get("PLATE_DENOISE_ENHANCE", "1") != "0"


def load_plate_denoiser():
    """
    CPU denoiser has no persistent resources; kept for API symmetry.
    """
    return None


def _denoise_plate(plate_roi: np.ndarray) -> np.ndarray:
    """
    Lightweight denoising tuned for small plate crops.
    """
    if plate_roi.size == 0:
        return plate_roi

    if plate_roi.dtype != np.uint8:
        plate_roi = plate_roi.astype(np.uint8)

    # Fast NLM preserves edges (characters) better than Gaussian blur.
    denoised = cv2.fastNlMeansDenoisingColored(
        plate_roi,
        None,
        h=_H,
        hColor=_HCOLOR,
        templateWindowSize=7,
        searchWindowSize=21,
    )

    if not _DO_ENHANCE:
        return denoised

    # Contrast + gentle sharpening to pop edges on small plates.
    gray = cv2.cvtColor(denoised, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    eq = clahe.apply(gray)
    blurred = cv2.GaussianBlur(eq, (0, 0), sigmaX=0.8, sigmaY=0.8)
    sharpen = cv2.addWeighted(eq, 1.0, blurred, -0.5, 0)
    return cv2.cvtColor(sharpen, cv2.COLOR_GRAY2BGR)


def process_plate_denoise(task: Task, _) -> dict:
    """
    Load plate crop from the frame store, denoise on CPU, and hand off the
    cleaned ROI for OCR.
    """
    payload_ref = task.meta.get("payload_ref")
    car_bbox = task.meta.get("car_bbox")
    plate_bbox = task.meta.get("plate_bbox")

    if payload_ref is None or car_bbox is None or plate_bbox is None:
        return {"plate_roi": None}

    frame = frame_store.load_frame(payload_ref)

    cx1, cy1, cx2, cy2 = map(int, car_bbox)
    car_roi = frame[cy1:cy2, cx1:cx2]
    if car_roi.size == 0:
        return {"plate_roi": None}

    px1, py1, px2, py2 = map(int, plate_bbox)
    plate_roi = car_roi[py1:py2, px1:px2]

    if plate_roi.size == 0:
        return {"plate_roi": None}

    denoised = _denoise_plate(plate_roi)

    global _debug_saved
    if DEBUG_SAVE_PATH and not _debug_saved and denoised is not None and denoised.size > 0:
        os.makedirs(os.path.dirname(DEBUG_SAVE_PATH) or ".", exist_ok=True)
        try:
            cv2.imwrite(DEBUG_SAVE_PATH, denoised)
            _debug_saved = True
        except Exception:
            # Best-effort debug save; ignore failures to keep pipeline running.
            pass

    return {"plate_roi": denoised, "car_bbox": car_bbox, "plate_bbox": plate_bbox}

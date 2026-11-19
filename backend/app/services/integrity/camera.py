"""Camera health measurements (T7 / S8): a covered, switched-off or frozen camera is not "nobody sitting there".

Per frame: near-black (mean gray) and near-uniform (gray standard deviation) images. Per pair of consecutive
frames: the mean absolute difference of their thumbnails, which is ~0 for a static image or a looped virtual
camera and clearly above the sensor-noise floor for a live one. Runs are judged by the policy.
"""
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from app.services.integrity import thresholds as t


@dataclass(frozen=True)
class FrameHealth:
    blocked: bool  # near-black or near-uniform
    thumbnail: np.ndarray


def measure_health(image: np.ndarray) -> FrameHealth:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    thumb = cv2.resize(gray, t.CAMERA_THUMB_SIZE, interpolation=cv2.INTER_AREA)
    mean, std = float(gray.mean()), float(gray.std())
    return FrameHealth(blocked=mean < t.CAMERA_DARK_MEAN or std < t.CAMERA_UNIFORM_STD, thumbnail=thumb)


def thumbnail_delta(previous: Optional[np.ndarray], current: np.ndarray) -> Optional[float]:
    """Mean absolute difference between two thumbnails; None when there is nothing to compare with."""
    if previous is None or previous.shape != current.shape:
        return None
    return float(np.abs(previous.astype(np.int16) - current.astype(np.int16)).mean())


def is_frozen(delta: Optional[float]) -> Optional[bool]:
    return None if delta is None else delta <= t.CAMERA_FROZEN_MAX_DIFF

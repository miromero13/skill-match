"""Calibration checks that have no supervision equivalent: lighting, framing, focus, screen patterns and the camera label.

The integrity engine measures faces, pose, identity, occlusion and camera health; these are the remaining pre-exam
checks of the guided calibration, kept next to it. None of them is a validated presentation-attack detector.

``camera_label`` is supplied by the client, so ``virtual_camera_label`` is **advisory**: a modified client can send
any label (or none) and nothing server-side can check it. The server-side signal against a virtual or looped camera is
the frozen/looped feed check in ``camera.py`` (the same one supervision uses): consecutive frames that are the same
image, plus the requirement of several different frames. The keyword check only rejects the honest case, where the
browser reports an obviously virtual device.
"""
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from app.services.integrity import thresholds as t


@dataclass(frozen=True)
class FrameEnvironment:
    """What one calibration frame says about the room and the picture (``measure``)."""

    brightness: float  # mean gray, 0-1
    size: tuple[int, int]  # (width, height)
    sharpness: Optional[float]  # Laplacian variance of the face crop; None without a face box
    screen_pattern: bool  # the face crop has the periodic texture of a screen (experimental heuristic)


def size_acceptable(size: tuple[int, int]) -> bool:
    (min_w, min_h), (max_w, max_h) = t.CAL_FRAME_MIN_SIZE, t.CAL_FRAME_MAX_SIZE
    return min_w <= size[0] <= max_w and min_h <= size[1] <= max_h


def screen_pattern(gray: np.ndarray) -> bool:
    """Experimental periodic-texture indicator (FFT peak share). It cannot rule out replay or deepfakes."""
    small = cv2.resize(gray, (96, 96)).astype(np.float32)
    spectrum = np.abs(np.fft.fftshift(np.fft.fft2(small - small.mean()))) ** 2
    spectrum[40:57, 40:57] = 0
    energy = float(spectrum.sum())
    return energy != 0 and float(spectrum.max()) / energy >= t.CAL_SCREEN_PEAK_SHARE


def measure(image: np.ndarray, face_box: Optional[tuple[float, float, float, float]]) -> FrameEnvironment:
    """Lighting, focus and screen texture of one frame; ``face_box`` is (x, y, w, h) as fractions of the frame."""
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    sharpness: Optional[float] = None
    pattern = False
    if face_box is not None:
        x, y, w, h = face_box
        crop = gray[max(0, int(y * height)):min(height, int((y + h) * height)),
                    max(0, int(x * width)):min(width, int((x + w) * width))]
        if crop.size:
            sharpness = float(cv2.Laplacian(crop, cv2.CV_64F).var())
            pattern = screen_pattern(crop)
    return FrameEnvironment(float(gray.mean()) / 255.0, (width, height), sharpness, pattern)


def lighting_ok(env: FrameEnvironment) -> bool:
    low, high = t.CAL_BRIGHTNESS_RANGE
    return low <= env.brightness <= high


def framing_ok(face_box: Optional[tuple[float, float, float, float]], face_score: Optional[float] = None) -> bool:
    """The face is confident, near the centre of the frame and big enough (an unboxed face is never well framed)."""
    if face_box is None or face_score is None or face_score < t.CAL_MIN_FACE_SCORE:
        return False
    x, y, w, h = face_box
    max_x, max_y = t.CAL_FACE_MAX_CENTER_OFFSET
    min_w, min_h = t.CAL_FACE_MIN_SIZE
    return abs(x + w / 2 - 0.5) <= max_x and abs(y + h / 2 - 0.5) <= max_y and w >= min_w and h >= min_h


def sharp_ok(env: FrameEnvironment) -> bool:
    return env.sharpness is not None and env.sharpness >= t.CAL_MIN_SHARPNESS


def virtual_camera_label(label: str) -> bool:
    """True when the client-reported device label names a virtual camera. Advisory: see the module docstring."""
    folded = (label or "").casefold()
    return any(name in folded for name in t.CAL_VIRTUAL_CAMERA_KEYWORDS)

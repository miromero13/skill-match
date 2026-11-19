"""Gaze measurement and the calibrated screen zone (S5).

Everything here is pure math over MediaPipe FaceLandmarker output so that supervision and calibration (T9)
share it. The browser computes the same features in ``frontend/src/services/gaze-tracking.ts``; the formulas
below are the contract and both sides are pinned by the same synthetic landmark fixtures.

Conventions: landmark coordinates are normalized image coordinates of the *unmirrored* camera frame.
``gaze_h`` is positive when the iris is toward the image right, ``gaze_v`` positive when it is down.
Head ``pitch`` is positive looking down and ``yaw`` positive toward the image right (see frame_analyzer).
"""
from dataclasses import dataclass
from statistics import median
from typing import Any, Mapping, Optional, Sequence

import numpy as np

from app.services.integrity import thresholds as t
from app.services.integrity.models import FrameBatch, FrameObservation

# (corner at the image-left, corner at the image-right, upper lid, lower lid, iris center)
EYES = (
    (33, 133, 159, 145, 468),
    (362, 263, 386, 374, 473),
)
IRIS_LANDMARK_COUNT = 478
TARGETS = ("CENTER", "TOP_LEFT", "TOP_RIGHT", "BOTTOM_LEFT", "BOTTOM_RIGHT")


@dataclass(frozen=True)
class GazeMeasurement:
    gaze_h: Optional[float]
    gaze_v: Optional[float]
    blink: bool


def _clip(value: float) -> float:
    return max(-1.0, min(1.0, value))


def measure_gaze(points: Any, blendshapes: Mapping[str, float]) -> GazeMeasurement:
    """Gaze from the iris centers relative to the eye corners (h) and lids (v), blended with eyeLook* blendshapes.

    ``points`` is an (N, >=2) array of normalized landmarks. Without iris landmarks (N < 478) or with a
    degenerate eye the gaze is ``None`` (never a clean "centered" reading).
    """
    pts = np.asarray(points, dtype=np.float64)
    horizontal: list[float] = []
    vertical: list[float] = []
    openings: list[float] = []
    if pts.ndim == 2 and pts.shape[0] >= IRIS_LANDMARK_COUNT and pts.shape[1] >= 2:
        for left, right, upper, lower, iris in EYES:
            axis = pts[right, :2] - pts[left, :2]
            width = float(np.hypot(axis[0], axis[1]))
            if width < 1e-4:
                continue
            u = axis / width
            down = np.array([-u[1], u[0]])  # the in-image perpendicular pointing down for an upright eye
            mid = (pts[left, :2] + pts[right, :2]) / 2.0
            horizontal.append(_clip(t.GAZE_GAIN_H * float(np.dot(pts[iris, :2] - mid, u)) / (width / 2.0)))
            opening = float(np.dot(pts[lower, :2] - pts[upper, :2], down))
            openings.append(opening / width)
            if opening > 1e-6:
                lid_mid = (pts[upper, :2] + pts[lower, :2]) / 2.0
                vertical.append(_clip(t.GAZE_GAIN_V * float(np.dot(pts[iris, :2] - lid_mid, down)) / (opening / 2.0)))

    blink = _is_blink(blendshapes, openings)
    if not horizontal or not vertical:
        return GazeMeasurement(None, None, blink)
    geo_h = sum(horizontal) / len(horizontal)
    geo_v = sum(vertical) / len(vertical)
    w = t.GAZE_BLENDSHAPE_WEIGHT
    if _has_gaze_blendshapes(blendshapes):
        bs = blendshapes.get
        bs_h = ((bs("eyeLookOutLeft", 0.0) + bs("eyeLookInRight", 0.0))
                - (bs("eyeLookInLeft", 0.0) + bs("eyeLookOutRight", 0.0))) / 2.0
        bs_v = ((bs("eyeLookDownLeft", 0.0) + bs("eyeLookDownRight", 0.0))
                - (bs("eyeLookUpLeft", 0.0) + bs("eyeLookUpRight", 0.0))) / 2.0
        return GazeMeasurement((1 - w) * geo_h + w * bs_h, (1 - w) * geo_v + w * bs_v, blink)
    return GazeMeasurement(geo_h, geo_v, blink)


def _has_gaze_blendshapes(blendshapes: Mapping[str, float]) -> bool:
    return any(name.startswith("eyeLook") for name in blendshapes)


def _is_blink(blendshapes: Mapping[str, float], opening_ratios: Sequence[float]) -> bool:
    if "eyeBlinkLeft" in blendshapes or "eyeBlinkRight" in blendshapes:
        score = (blendshapes.get("eyeBlinkLeft", 0.0) + blendshapes.get("eyeBlinkRight", 0.0)) / 2.0
        return score >= t.GAZE_BLINK_SCORE
    return bool(opening_ratios) and all(ratio < t.GAZE_CLOSED_LID_RATIO for ratio in opening_ratios)


# ---- calibrated screen zone -----------------------------------------------------------------------


@dataclass(frozen=True)
class GazeZone:
    """Bounds of (head pitch/yaw in degrees, gaze_h/gaze_v) while the candidate looks at the screen."""

    pitch_min: float
    pitch_max: float
    yaw_min: float
    yaw_max: float
    gaze_h_min: float
    gaze_h_max: float
    gaze_v_min: float
    gaze_v_max: float

    def to_dict(self) -> dict[str, float]:
        return {name: float(getattr(self, name)) for name in self.__dataclass_fields__}

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "GazeZone":
        return cls(**{name: float(raw[name]) for name in cls.__dataclass_fields__})


DEFAULT_ZONE = GazeZone(
    t.DEFAULT_ZONE_PITCH_DEG[0], t.DEFAULT_ZONE_PITCH_DEG[1],
    t.DEFAULT_ZONE_YAW_DEG[0], t.DEFAULT_ZONE_YAW_DEG[1],
    t.DEFAULT_ZONE_GAZE_H[0], t.DEFAULT_ZONE_GAZE_H[1],
    t.DEFAULT_ZONE_GAZE_V[0], t.DEFAULT_ZONE_GAZE_V[1],
)


class GazeCalibrationError(Exception):
    """The calibration frames cannot yield a trustworthy zone; ``code`` says why (the API maps it to a message)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _usable(frame: FrameObservation) -> bool:
    return (
        frame.face_count == 1 and not frame.blink and frame.gaze_h is not None and frame.gaze_v is not None
        and frame.pitch_deg is not None and frame.yaw_deg is not None
    )


def compute_zone(per_target: Mapping[str, FrameBatch]) -> GazeZone:
    """The zone spanned by the five calibration targets (center + four corners) plus a margin.

    Per target the median of its usable frames is taken so a stray frame cannot widen the zone. Raises
    ``GazeCalibrationError`` when a face is missing or doubled, the gaze models are unavailable or the
    targets cannot be told apart (the candidate did not really look at the corners).
    """
    batches = {name: per_target.get(name, FrameBatch()) for name in TARGETS}
    if any(batch.model_unavailable for batch in batches.values()):
        raise GazeCalibrationError("MODEL_UNAVAILABLE")
    if any(f.face_count > 1 for batch in batches.values() for f in batch.frames):
        raise GazeCalibrationError("MULTIPLE_FACES")
    medians: list[tuple[float, float, float, float]] = []
    for batch in batches.values():
        single = [f for f in batch.frames if f.face_count == 1]
        usable = [f for f in single if _usable(f)]
        if len(usable) < t.ZONE_MIN_USABLE_FRAMES:
            # One face was seen but the landmarker could not measure the eyes: the model is the problem.
            if any(f.gaze_h is None for f in single if not f.blink):
                raise GazeCalibrationError("MODEL_UNAVAILABLE")
            raise GazeCalibrationError("FACE_MISSING")
        medians.append((
            median(float(f.pitch_deg) for f in usable if f.pitch_deg is not None),
            median(float(f.yaw_deg) for f in usable if f.yaw_deg is not None),
            median(float(f.gaze_h) for f in usable if f.gaze_h is not None),
            median(float(f.gaze_v) for f in usable if f.gaze_v is not None),
        ))
    pitch, yaw, gaze_h, gaze_v = zip(*medians)

    def span(values: Sequence[float]) -> float:
        return max(values) - min(values)

    horizontal_ok = span(yaw) >= t.ZONE_MIN_HEAD_SPAN_DEG or span(gaze_h) >= t.ZONE_MIN_GAZE_SPAN
    vertical_ok = span(pitch) >= t.ZONE_MIN_HEAD_SPAN_DEG or span(gaze_v) >= t.ZONE_MIN_GAZE_SPAN
    if not (horizontal_ok and vertical_ok):
        raise GazeCalibrationError("NOT_DISTINGUISHABLE")
    head, eyes = t.ZONE_HEAD_MARGIN_DEG, t.ZONE_GAZE_MARGIN
    return GazeZone(
        pitch_min=min(pitch) - head, pitch_max=max(pitch) + head,
        yaw_min=min(yaw) - head, yaw_max=max(yaw) + head,
        gaze_h_min=min(gaze_h) - eyes, gaze_h_max=max(gaze_h) + eyes,
        gaze_v_min=min(gaze_v) - eyes, gaze_v_max=max(gaze_v) + eyes,
    )

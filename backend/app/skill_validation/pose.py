"""View-robust pose signature: joint angles from MediaPipe 3D world landmarks.

The model (`pose_landmarker_full.task`, Apache-2.0) is provisioned by `scripts/install_vision_models.py`
(SHA-256 pinned); nothing here downloads anything. Angles between body segments do not depend on where
the camera stands, so two people recorded from different angles produce comparable signatures.
"""
from __future__ import annotations

import logging
import math
import warnings
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger("skillmatch.skill_validation.pose")

POSE_MODEL_FILENAME = "pose_landmarker_full.task"
POSE_MODEL_NAME = "mediapipe-pose-landmarker-full"
SAMPLE_FPS = 10.0
MAX_ANALYZED_SECONDS = 120.0
MAX_FRAME_SIDE = 640
VISIBILITY_THRESHOLD = 0.5

# MediaPipe pose landmark indices.
_L_SHOULDER, _R_SHOULDER, _L_ELBOW, _R_ELBOW, _L_WRIST, _R_WRIST = 11, 12, 13, 14, 15, 16
_L_HIP, _R_HIP, _L_KNEE, _R_KNEE, _L_ANKLE, _R_ANKLE = 23, 24, 25, 26, 27, 28
_L_FOOT, _R_FOOT = 31, 32

# (feature name, (a, b, c)): angle at b between b->a and b->c. "trunk" is the inclination of the
# hip-center -> shoulder-center segment against the vertical.
JOINTS: tuple[tuple[str, tuple[int, ...]], ...] = (
    ("l_elbow", (_L_SHOULDER, _L_ELBOW, _L_WRIST)),
    ("r_elbow", (_R_SHOULDER, _R_ELBOW, _R_WRIST)),
    ("l_shoulder", (_L_HIP, _L_SHOULDER, _L_ELBOW)),
    ("r_shoulder", (_R_HIP, _R_SHOULDER, _R_ELBOW)),
    ("l_hip", (_L_SHOULDER, _L_HIP, _L_KNEE)),
    ("r_hip", (_R_SHOULDER, _R_HIP, _R_KNEE)),
    ("l_hip_abd", (_R_HIP, _L_HIP, _L_KNEE)),
    ("r_hip_abd", (_L_HIP, _R_HIP, _R_KNEE)),
    ("l_knee", (_L_HIP, _L_KNEE, _L_ANKLE)),
    ("r_knee", (_R_HIP, _R_KNEE, _R_ANKLE)),
    ("l_ankle", (_L_KNEE, _L_ANKLE, _L_FOOT)),
    ("r_ankle", (_R_KNEE, _R_ANKLE, _R_FOOT)),
    ("trunk", (_L_SHOULDER, _R_SHOULDER, _L_HIP, _R_HIP)),
)
FEATURE_NAMES: list[str] = [name for name, _ in JOINTS]
FEATURE_COUNT = len(FEATURE_NAMES)

# Column permutation that swaps the left and right side (mirrored performance).
MIRROR_INDEX: list[int] = [
    FEATURE_NAMES.index(name.replace("l_", "r_", 1) if name.startswith("l_") else
                        name.replace("r_", "l_", 1) if name.startswith("r_") else name)
    for name in FEATURE_NAMES
]

# Prior relevance per feature: ankles and hip abduction are the noisiest estimates.
PRIOR_WEIGHTS = np.array(
    [0.8, 0.8, 1.0, 1.0, 1.0, 1.0, 0.6, 0.6, 1.0, 1.0, 0.5, 0.5, 0.8], dtype=np.float64
)


def pose_model_path() -> Path:
    """Resolved at call time so a deployment (or a test) can relocate the weights."""
    from app.services.vision_models import MODELS_DIR

    return MODELS_DIR / POSE_MODEL_FILENAME


def _angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    u, v = a - b, c - b
    nu, nv = float(np.linalg.norm(u)), float(np.linalg.norm(v))
    if nu < 1e-6 or nv < 1e-6:
        return math.nan
    cos = float(np.dot(u, v) / (nu * nv))
    return math.degrees(math.acos(max(-1.0, min(1.0, cos))))


def landmarks_to_features(world: np.ndarray, visibility: np.ndarray) -> tuple[list[float], list[float]]:
    """Angles (degrees, 0-180) and per-feature visibility from 33x3 world landmarks (y points down)."""
    angles: list[float] = []
    vis: list[float] = []
    for name, idx in JOINTS:
        if name == "trunk":
            mid_shoulder = (world[idx[0]] + world[idx[1]]) / 2.0
            mid_hip = (world[idx[2]] + world[idx[3]]) / 2.0
            up = np.array([0.0, -1.0, 0.0])
            angles.append(_angle(mid_hip + up, mid_hip, mid_shoulder))
        else:
            angles.append(_angle(world[idx[0]], world[idx[1]], world[idx[2]]))
        vis.append(float(min(visibility[i] for i in idx)))
    return angles, vis


def _smooth_runs(values: np.ndarray, present: np.ndarray) -> np.ndarray:
    """Median-3 then mean-3 per feature over each contiguous run of detected frames."""
    out = values.copy()
    n = len(values)
    start = 0
    while start < n:
        if not present[start]:
            start += 1
            continue
        end = start
        while end + 1 < n and present[end + 1]:
            end += 1
        run = values[start:end + 1]
        if len(run) >= 3:
            padded = np.vstack([run[:1], run, run[-1:]])
            stacked = np.stack([padded[:-2], padded[1:-1], padded[2:]])
            med = np.nanmedian(stacked, axis=0) if np.isnan(stacked).any() else np.median(stacked, axis=0)
            padded = np.vstack([med[:1], med, med[-1:]])
            stacked = np.stack([padded[:-2], padded[1:-1], padded[2:]])
            with np.errstate(all="ignore"):
                mean = np.nanmean(stacked, axis=0) if np.isnan(stacked).any() else stacked.mean(axis=0)
            out[start:end + 1] = mean
        start = end + 1
    return out


def build_signature(
    rows: list[tuple[list[float], list[float]] | None], fps: float
) -> dict[str, Any]:
    """Compact JSON pose block from per-sampled-frame (angles, visibility) or ``None`` (nobody)."""
    total = len(rows)
    present = np.array([row is not None for row in rows], dtype=bool)
    detected = int(present.sum())
    angles = np.full((total, FEATURE_COUNT), np.nan)
    vis = np.zeros((total, FEATURE_COUNT))
    for i, row in enumerate(rows):
        if row is not None:
            angles[i] = row[0]
            vis[i] = row[1]
    if detected:
        with warnings.catch_warnings(), np.errstate(all="ignore"):
            warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN joints in a run stay NaN
            angles = _smooth_runs(angles, present)
    signature: list[list[float | None] | None] = []
    visibility: list[list[float] | None] = []
    for i in range(total):
        if not present[i]:
            signature.append(None)
            visibility.append(None)
            continue
        signature.append([None if not math.isfinite(v) else round(float(v), 1) for v in angles[i]])
        visibility.append([round(float(v), 1) for v in np.clip(vis[i], 0.0, 1.0)])
    return {
        "model": POSE_MODEL_NAME,
        "fps": round(float(fps), 3),
        "features": list(FEATURE_NAMES),
        "frames_sampled": total,
        "frames_detected": detected,
        "detected_ratio": round(detected / total, 3) if total else 0.0,
        "signature": signature,
        "visibility": visibility,
    }


class PoseExtractor:
    """MediaPipe PoseLandmarker in VIDEO mode (stateful tracking); one instance per video."""

    def __init__(self, model_path: Path) -> None:
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        self._mp = mp
        options = vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(options)

    def process(self, rgb: np.ndarray, timestamp_ms: int) -> tuple[list[float], list[float]] | None:
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        result = self._landmarker.detect_for_video(image, timestamp_ms)
        if not result.pose_world_landmarks:
            return None
        world_lms = result.pose_world_landmarks[0]
        image_lms = result.pose_landmarks[0] if result.pose_landmarks else world_lms
        world = np.array([[lm.x, lm.y, lm.z] for lm in world_lms], dtype=np.float64)
        visibility = np.array(
            [float(lm.visibility) if lm.visibility is not None else 0.0 for lm in image_lms],
            dtype=np.float64,
        )
        if world.shape != (33, 3) or len(visibility) != 33:
            return None
        return landmarks_to_features(world, visibility)

    def close(self) -> None:
        try:
            self._landmarker.close()
        except Exception:  # pragma: no cover - best effort
            logger.debug("PoseLandmarker close failed", exc_info=True)

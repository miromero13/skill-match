"""EfficientDet-Lite0 ("sports ball", COCO) ball detector fused with the classical tracker.

The model (`efficientdet_lite0.tflite`, Apache-2.0) is provisioned at image build by
`scripts/install_vision_models.py` (SHA-256 pinned); nothing here downloads anything.
Both detectors implement `BallDetectorProtocol`, so `track_ball_in_video` keeps its
Kalman smoothing, gap filling and plausibility checks unchanged.
"""
from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np

from app.football.config import BallTrackerConfig, load_football_config
from app.football.pipeline.ball_tracker import (
    DETECTION_TARGET_WIDTH,
    BallDetectorProtocol,
    ClassicalMOG2HoughDetector,
)

EFFICIENTDET_MODEL_FILENAME = "efficientdet_lite0.tflite"
SPORTS_BALL_CATEGORY = "sports ball"
DEFAULT_SCORE_THRESHOLD = 0.2

# EfficientDet-Lite0 costs ~30 ms per frame on CPU whatever the input size, so it
# runs at about this rate; the classical detector covers the frames in between.
DEFAULT_MODEL_HZ = 6.0

# While the model has seen the ball recently, a classical candidate far from the
# last accepted position is most likely a different round object (lamp, head,
# logo), so it is ignored for this frame.
_MODEL_RECENT_FRAMES = 12
_GATE_MIN_FRACTION_OF_WIDTH = 0.25
_GATE_RADII = 6.0


def efficientdet_model_path() -> Path:
    """Resolved at call time so a deployment (or a test) can relocate the weights."""
    from app.services.vision_models import MODELS_DIR

    return MODELS_DIR / EFFICIENTDET_MODEL_FILENAME


class MediaPipeEfficientDetBallDetector:
    """`BallDetectorProtocol` over MediaPipe Tasks `ObjectDetector` (IMAGE mode, CPU)."""

    def __init__(
        self,
        model_path: str | Path,
        score_threshold: float = DEFAULT_SCORE_THRESHOLD,
        max_results: int = 3,
    ) -> None:
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        self._mp = mp
        options = vision.ObjectDetectorOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.IMAGE,
            score_threshold=score_threshold,
            max_results=max_results,
            category_allowlist=[SPORTS_BALL_CATEGORY],
        )
        self._detector = vision.ObjectDetector.create_from_options(options)

    def detect(
        self, frame_bgr: np.ndarray, frame_idx: int
    ) -> tuple[float, float, float, float] | None:
        rgb = np.ascontiguousarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        result = self._detector.detect(image)
        best: tuple[float, float, float, float] | None = None
        for detection in result.detections:
            if not detection.categories:
                continue
            category = detection.categories[0]
            if category.category_name != SPORTS_BALL_CATEGORY:
                continue
            score = float(category.score or 0.0)
            if best is not None and score <= best[3]:
                continue
            box = detection.bounding_box
            cx = box.origin_x + box.width / 2.0
            cy = box.origin_y + box.height / 2.0
            radius = max(1.0, (box.width + box.height) / 4.0)
            best = (float(cx), float(cy), float(radius), score)
        return best

    def close(self) -> None:
        self._detector.close()


class FusedEfficientDetClassicalDetector:
    """
    Per frame: prefer the EfficientDet detection, fall back to the classical
    MOG2/Hough detector. The classical detector runs on every frame so its
    background model stays current; the model runs every `model_stride` frames
    (about `model_hz` times per second of video). Frames wider than `DETECTION_TARGET_WIDTH`
    are downscaled first (like the built-in path of `track_ball_in_video`) and
    detections are mapped back to the original resolution.
    """

    def __init__(
        self,
        model_detector: BallDetectorProtocol,
        frame_width: int,
        fps: float = 30.0,
        model_hz: float = DEFAULT_MODEL_HZ,
        config: BallTrackerConfig | None = None,
    ) -> None:
        cfg = config or load_football_config().ball_tracker
        self.model_detector = model_detector
        self.model_stride = max(1, round(max(1.0, fps) / max(0.1, model_hz)))
        self.scale = (
            DETECTION_TARGET_WIDTH / float(frame_width)
            if frame_width > DETECTION_TARGET_WIDTH
            else 1.0
        )
        self.classical = ClassicalMOG2HoughDetector(
            min_radius_px=max(1, round(cfg.min_radius_px * self.scale)),
            max_radius_px=max(2, round(cfg.max_radius_px * self.scale)),
        )
        self.model_frames = 0
        self.classical_frames = 0
        self._last_model_frame: int | None = None
        self._last_accepted: tuple[float, float, float] | None = None

    def detect(
        self, frame_bgr: np.ndarray, frame_idx: int
    ) -> tuple[float, float, float, float] | None:
        if self.scale < 1.0:
            frame = cv2.resize(
                frame_bgr, None, fx=self.scale, fy=self.scale, interpolation=cv2.INTER_AREA
            )
        else:
            frame = frame_bgr

        classical = self.classical.detect(frame, frame_idx)
        model = (
            self.model_detector.detect(frame, frame_idx)
            if frame_idx % self.model_stride == 0
            else None
        )

        chosen: tuple[float, float, float, float] | None = None
        if model is not None:
            self._last_model_frame = frame_idx
            self.model_frames += 1
            chosen = model
        elif classical is not None and self._classical_plausible(classical, frame_idx, frame):
            self.classical_frames += 1
            chosen = classical

        if chosen is None:
            return None
        x, y, r, conf = chosen
        self._last_accepted = (x, y, r)
        return x / self.scale, y / self.scale, r / self.scale, conf

    def _classical_plausible(
        self,
        candidate: tuple[float, float, float, float],
        frame_idx: int,
        frame: np.ndarray,
    ) -> bool:
        if (
            self._last_model_frame is None
            or self._last_accepted is None
            or frame_idx - self._last_model_frame > _MODEL_RECENT_FRAMES
        ):
            return True
        ax, ay, ar = self._last_accepted
        max_dist = max(_GATE_RADII * ar, _GATE_MIN_FRACTION_OF_WIDTH * frame.shape[1])
        return math.hypot(candidate[0] - ax, candidate[1] - ay) <= max_dist

    def close(self) -> None:
        close = getattr(self.model_detector, "close", None)
        if callable(close):
            close()

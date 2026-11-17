from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np

from app.football.config import BallTrackerConfig, load_football_config


@dataclass
class BallFramePoint:
    frame_idx: int
    t_ms: int
    x: float
    y: float
    radius: float
    confidence: float
    interpolated: bool = False
    height_diameters: float = 0.0
    is_ground_level: bool = False


@dataclass
class BallTrack:
    points: list[BallFramePoint] = field(default_factory=list)
    fps: float = 30.0
    frame_width: int = 640
    frame_height: int = 360
    median_radius_px: float = 24.0
    baseline_y_px: float = 280.0
    ground_y_px: float | None = None


class BallDetectorProtocol(Protocol):
    """
    Swappable ball detector interface.
    Default implementation uses classical vision (MOG2 + Hough/contours);
    future TrackNet-style ONNX models implement this same protocol.
    """

    def detect(
        self, frame_bgr: np.ndarray, frame_idx: int
    ) -> tuple[float, float, float, float] | None:
        """Return `(x, y, radius, confidence)` or `None` if no ball is detected."""


class ClassicalMOG2HoughDetector:
    """
    Classical computer vision ball detector combining:
    1. MOG2 background subtraction + morphological opening/closing
    2. Circularity-filtered foreground contour / brightness detection with skin-tone suppression
    3. Motion-restricted HoughCircles refinement avoiding human faces and body parts
    """

    def __init__(self, min_radius_px: int = 8, max_radius_px: int = 160) -> None:
        self.min_radius_px = min_radius_px
        self.max_radius_px = max_radius_px
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=120, varThreshold=25.0, detectShadows=False
        )
        self.kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

    def _is_skin_dominated(
        self, frame_bgr: np.ndarray, cx: float, cy: float, radius: float
    ) -> bool:
        """Reject regions dominated by human skin tone (faces, arms, hands)."""
        r_inner = max(4.0, radius * 0.7)
        x1, y1 = max(0, int(cx - r_inner)), max(0, int(cy - r_inner))
        x2, y2 = min(frame_bgr.shape[1], int(cx + r_inner)), min(
            frame_bgr.shape[0], int(cy + r_inner)
        )
        if x2 <= x1 or y2 <= y1:
            return False
        roi = frame_bgr[y1:y2, x1:x2]
        if roi.size == 0:
            return False
        ycrcb = cv2.cvtColor(roi, cv2.COLOR_BGR2YCrCb)
        # Standard skin tone range: 133 <= Cr <= 173 and 77 <= Cb <= 127
        skin_mask = cv2.inRange(
            ycrcb,
            np.array([0, 133, 77], dtype=np.uint8),
            np.array([255, 173, 127], dtype=np.uint8),
        )
        return bool(np.mean(skin_mask > 0) > 0.38)

    def detect(
        self, frame_bgr: np.ndarray, frame_idx: int
    ) -> tuple[float, float, float, float] | None:
        fg_mask = self.bg_subtractor.apply(frame_bgr)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, self.kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, self.kernel)

        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 1.2)

        # Combine foreground motion mask with high-brightness ball mask so stationary apex frames stay tracked
        _, bright_mask = cv2.threshold(blurred, 200, 255, cv2.THRESH_BINARY)
        combined_mask = cv2.bitwise_or(fg_mask, bright_mask)

        contours, _ = cv2.findContours(
            combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        best_candidate: tuple[float, float, float, float] | None = None
        best_score = 0.0

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < math.pi * (self.min_radius_px * 0.6) ** 2:
                continue
            perimeter = cv2.arcLength(cnt, True)
            if perimeter <= 1e-3:
                continue
            circularity = (4.0 * math.pi * area) / (perimeter * perimeter)
            if circularity < 0.45:
                continue
            (cx, cy), radius = cv2.minEnclosingCircle(cnt)
            if not (self.min_radius_px <= radius <= self.max_radius_px):
                continue
            if self._is_skin_dominated(frame_bgr, cx, cy, radius):
                continue
            score = min(1.0, circularity)
            if score > best_score:
                best_score = score
                best_candidate = (float(cx), float(cy), float(radius), float(score))

        if best_candidate is not None:
            return best_candidate

        # Fallback: HoughCircles only if motion mask is non-empty and target is not skin
        if np.mean(fg_mask > 0) > 0.005:
            circles = cv2.HoughCircles(
                blurred,
                cv2.HOUGH_GRADIENT,
                dp=1.2,
                minDist=float(self.min_radius_px * 2),
                param1=100.0,
                param2=30.0,
                minRadius=self.min_radius_px,
                maxRadius=self.max_radius_px,
            )
            if circles is not None and len(circles) > 0:
                for c in circles[0]:
                    cand_x, cand_y, cand_r = float(c[0]), float(c[1]), float(c[2])
                    if not self._is_skin_dominated(frame_bgr, cand_x, cand_y, cand_r):
                        return cand_x, cand_y, cand_r, 0.70

        return None


class ConstantVelocityKalman2D:
    """Linear 4-state (`[x, y, vx, vy]`) constant-velocity Kalman filter."""

    def __init__(self, dt: float = 1.0 / 30.0) -> None:
        self.dt = dt
        self.state = np.zeros((4, 1), dtype=np.float64)
        self.cov = np.eye(4, dtype=np.float64) * 500.0
        self.initialized = False

        self.F = np.array(
            [
                [1.0, 0.0, dt, 0.0],
                [0.0, 1.0, 0.0, dt],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )
        self.H = np.array(
            [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
            ],
            dtype=np.float64,
        )
        self.Q = np.diag([2.0, 2.0, 80.0, 160.0]).astype(np.float64)
        self.R = np.diag([4.0, 4.0]).astype(np.float64)

    def predict(self) -> tuple[float, float]:
        if not self.initialized:
            return 0.0, 0.0
        self.state = self.F @ self.state
        self.cov = self.F @ self.cov @ self.F.T + self.Q
        return float(self.state[0, 0]), float(self.state[1, 0])

    def update(self, meas_x: float, meas_y: float) -> tuple[float, float]:
        z = np.array([[meas_x], [meas_y]], dtype=np.float64)
        if not self.initialized:
            self.state[0, 0] = meas_x
            self.state[1, 0] = meas_y
            self.state[2, 0] = 0.0
            self.state[3, 0] = 0.0
            self.initialized = True
            return meas_x, meas_y

        y_res = z - (self.H @ self.state)
        s_mat = self.H @ self.cov @ self.H.T + self.R
        k_gain = self.cov @ self.H.T @ np.linalg.inv(s_mat)
        self.state = self.state + (k_gain @ y_res)
        eye4 = np.eye(4, dtype=np.float64)
        self.cov = (eye4 - k_gain @ self.H) @ self.cov
        return float(self.state[0, 0]), float(self.state[1, 0])


def _fill_short_gaps(
    raw_points: list[BallFramePoint | None],
    fps: float,
    max_gap_frames: int,
) -> list[BallFramePoint]:
    """
    Linearly interpolate missing detections for gaps up to `max_gap_frames` frames.
    """
    n = len(raw_points)
    filled: list[BallFramePoint | None] = list(raw_points)

    idx = 0
    while idx < n:
        if filled[idx] is not None:
            idx += 1
            continue
        gap_start = idx
        while idx < n and filled[idx] is None:
            idx += 1
        gap_end = idx - 1
        gap_len = gap_end - gap_start + 1

        prev_pt = filled[gap_start - 1] if gap_start > 0 else None
        next_pt = filled[gap_end + 1] if (gap_end + 1) < n else None

        if (
            gap_len <= max_gap_frames
            and prev_pt is not None
            and next_pt is not None
        ):
            for step in range(1, gap_len + 1):
                alpha = step / float(gap_len + 1)
                frame_i = gap_start + step - 1
                t_ms = round((frame_i * 1000.0) / fps)
                interp_x = prev_pt.x + alpha * (next_pt.x - prev_pt.x)
                interp_y = prev_pt.y + alpha * (next_pt.y - prev_pt.y)
                interp_r = prev_pt.radius + alpha * (next_pt.radius - prev_pt.radius)
                interp_conf = min(prev_pt.confidence, next_pt.confidence) * 0.75
                filled[frame_i] = BallFramePoint(
                    frame_idx=frame_i,
                    t_ms=t_ms,
                    x=interp_x,
                    y=interp_y,
                    radius=interp_r,
                    confidence=interp_conf,
                    interpolated=True,
                )

    return [pt for pt in filled if pt is not None]


def track_ball_in_video(
    video_path: str | Path,
    detector: BallDetectorProtocol | None = None,
    config: BallTrackerConfig | None = None,
) -> BallTrack:
    """
    Pure pipeline step (`ball_tracker`):
    video -> `BallTrack` (`t_ms, x, y, radius, confidence, height_diameters`).
    """
    cfg = config or load_football_config().ball_tracker
    active_detector = detector or ClassicalMOG2HoughDetector(
        min_radius_px=cfg.min_radius_px,
        max_radius_px=cfg.max_radius_px,
    )

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Could not open video file: {video_path}")

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    if fps <= 0:
        fps = 30.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 360)

    kalman = ConstantVelocityKalman2D(dt=1.0 / fps)
    raw_detections: list[BallFramePoint | None] = []
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            break

        kalman.predict()
        detection = active_detector.detect(frame, frame_idx)
        t_ms = round((frame_idx * 1000.0) / fps)

        if detection is not None:
            dx, dy, dr, dconf = detection
            kx, ky = kalman.update(dx, dy)
            # Blend measurement with Kalman state to preserve sharp touch rebounds
            fx = 0.75 * dx + 0.25 * kx
            fy = 0.75 * dy + 0.25 * ky
            raw_detections.append(
                BallFramePoint(
                    frame_idx=frame_idx,
                    t_ms=t_ms,
                    x=fx,
                    y=fy,
                    radius=dr,
                    confidence=dconf,
                    interpolated=False,
                )
            )
        else:
            raw_detections.append(None)

        frame_idx += 1

    cap.release()

    points = _fill_short_gaps(
        raw_points=raw_detections,
        fps=fps,
        max_gap_frames=cfg.max_gap_frames,
    )

    if not points:
        return BallTrack(
            points=[],
            fps=fps,
            frame_width=width,
            frame_height=height,
            median_radius_px=24.0,
            baseline_y_px=float(height),
        )

    radii = np.array([pt.radius for pt in points], dtype=np.float64)
    median_radius = float(np.median(radii))
    ball_diameter_px = max(2.0, 2.0 * median_radius)

    y_vals = np.array([pt.y for pt in points], dtype=np.float64)
    non_interp_count = sum(1 for pt in points if not pt.interpolated)
    vertical_span = float(np.max(y_vals) - np.min(y_vals))

    # In football juggling, a moving ball must have at least 0.8 ball diameters of vertical travel,
    # sufficient true detections, and must be below head level (median y in lower/middle frame).
    # Stationary background circles, head tremors, or ceiling lights are rejected.
    median_y = float(np.median(y_vals))
    if non_interp_count < 8 or vertical_span < (0.8 * ball_diameter_px) or median_y < (0.28 * height):
        return BallTrack(
            points=[],
            fps=fps,
            frame_width=width,
            frame_height=height,
            median_radius_px=median_radius,
            baseline_y_px=float(height),
        )

    # 95th percentile of image y (lowest physical position of the ball at foot level)
    baseline_y = float(np.percentile(y_vals, 95))

    # Real floor estimate: the absolute lowest position the ball reached (max y).
    # A dropped ball that bounces off the ground goes lower than normal foot-level
    # touches; a point counts as ground-level only when it sits close to that
    # absolute floor AND clearly below the typical foot-level baseline, so normal
    # rebound noise around the baseline is not misclassified as a ground bounce.
    absolute_floor_y = float(np.max(y_vals))
    ground_margin_px = max(4.0, 0.25 * ball_diameter_px)
    ground_y: float | None = None
    if (absolute_floor_y - baseline_y) >= (0.6 * ball_diameter_px):
        ground_y = absolute_floor_y

    for pt in points:
        pt.height_diameters = max(0.0, (baseline_y - pt.y) / ball_diameter_px)
        pt.is_ground_level = (
            ground_y is not None and (ground_y - pt.y) <= ground_margin_px
        )

    return BallTrack(
        points=points,
        fps=fps,
        frame_width=width,
        frame_height=height,
        median_radius_px=median_radius,
        baseline_y_px=baseline_y,
        ground_y_px=ground_y,
    )

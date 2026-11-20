"""Juggling touch counter for the `BALL_TOUCH_STREAK` metric (odd/tasks/skill-validation-engine.md, S6).

Local only (AGENTS.md §1.1): the pinned MediaPipe EfficientDet-Lite0 COCO detector ("sports ball" and "person")
runs on downscaled frames at ~25-30 Hz. While the ball is tracked the detector looks at a square crop around the
predicted ball position, so a small ball still fills enough of the 320 px model input; when the ball is lost it
looks at the whole frame and at the lower body of the person. Video time is split into short chunks processed in
parallel (one detector per worker), so the cost stays below the clip duration on a laptop CPU.

Counting is a pure function of the ball trajectory: short gaps are bridged, the vertical position is lightly
smoothed and every bottom turning point (ball moving down, then up) with a prominence of at least
``PROMINENCE_DIAMETERS`` ball diameters is one contact; contacts closer than ``NMS_SECONDS`` merge. A contact whose
ball bottom lands below the person's feet line (EfficientDet "person" box) with a weak rebound is a ground contact:
it is not a touch and it ends the streak. Without a visible person no contact is classified as ground. A streak
also ends when two touches are more than ``DROP_GAP_S`` apart (the ball was lost or dropped), the same rule as the
football pipeline. Nothing is invented: no ball, no touches.
"""
from __future__ import annotations

import logging
import math
import os
import threading
from collections import deque
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import cv2
import numpy as np
from scipy.signal import find_peaks

logger = logging.getLogger("skillmatch.skill_validation.ball_touches")

BALL_LABEL = "sports ball"
PERSON_LABEL = "person"
DETECTOR_NAME = "efficientdet-lite0-roi"

MAX_SECONDS = 180.0
MIN_SAMPLE_HZ = 20.0  # frames are sampled at the highest integer stride that keeps at least this rate
STORE_MAX_SIDE = 640  # frames are downscaled to this long side before any detection
CHUNK_SECONDS = 2.0  # video time per parallel work unit (tracker state restarts per chunk)
MIN_CHUNK_SECONDS = 0.75
WARMUP_SECONDS = 0.3  # end of the previous chunk replayed to seed the tracker of the next one
MAX_WORKERS = 4

DETECT_SCORE_MIN = 0.05  # detector threshold (candidates)
TRACK_SCORE_MIN = 0.06  # candidate accepted while tracking (gated by position and size)
ACQUIRE_SCORE_MIN = 0.15  # candidate accepted with no recent track (near the person when one is seen)
PERSON_SCORE_MIN = 0.30
CROP_DIAMETERS = 4.0  # tracking crop side, in ball diameters (a big ball in the 320 px model input)
RETRY_CROP_DIAMETERS = 8.0  # second, wider look (fast motion, or a ball the model prefers to see smaller)
MIN_CROP_SIDE = 96
LOST_AFTER_S = 0.30  # without an accepted detection for this long -> search the whole frame again
GATE_BASE_DIAMETERS = 1.5
GATE_SPEED_DIAMETERS_PER_S = 25.0

BRIDGE_S = 0.45  # gaps up to this long are interpolated inside one trajectory segment
PROMINENCE_DIAMETERS = 0.25
NMS_SECONDS = 0.18
# Ground contact: a bottom turning point with the ball bottom below the person's feet line AND a weak rebound
# (a bounce on the floor loses height; a foot touch sends the ball up again). Both are required because perspective
# puts a ball juggled in front of the player at about the feet line in the image.
GROUND_FEET_MARGIN_DIAMETERS = 0.15  # ball bottom at least this far below the feet line
GROUND_REBOUND_RATIO = 0.6
REBOUND_WINDOW_S = 0.6
DROP_GAP_S = 2.2  # same rule as app.football.pipeline.features.DROP_GAP_S


class ObjectDetector(Protocol):
    """``detect(image_bgr) -> [(label, score, cx, cy, width, height)]`` in image pixel coordinates."""

    def detect(self, image_bgr: np.ndarray) -> list[tuple[str, float, float, float, float, float]]: ...

    def close(self) -> None: ...


DetectorFactory = Callable[[], ObjectDetector]


class EfficientDetObjectDetector:
    """MediaPipe Tasks ``ObjectDetector`` over the pinned EfficientDet-Lite0 model (IMAGE mode, CPU)."""

    def __init__(self, model_path: str | Path, score_threshold: float = DETECT_SCORE_MIN, max_results: int = 8):
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        self._mp = mp
        options = vision.ObjectDetectorOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.IMAGE,
            score_threshold=score_threshold,
            max_results=max_results,
            category_allowlist=[BALL_LABEL, PERSON_LABEL],
        )
        self._detector = vision.ObjectDetector.create_from_options(options)

    def detect(self, image_bgr: np.ndarray) -> list[tuple[str, float, float, float, float, float]]:
        rgb = np.ascontiguousarray(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))
        result = self._detector.detect(self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb))
        out: list[tuple[str, float, float, float, float, float]] = []
        for detection in result.detections:
            if not detection.categories:
                continue
            category = detection.categories[0]
            box = detection.bounding_box
            out.append((
                str(category.category_name), float(category.score or 0.0),
                box.origin_x + box.width / 2.0, box.origin_y + box.height / 2.0, float(box.width), float(box.height),
            ))
        return out

    def close(self) -> None:
        self._detector.close()


@dataclass(frozen=True)
class BallSample:
    """One analyzed instant: ball centre/diameter (``None`` when not seen) in stored-frame pixels."""

    t: float
    x: float | None = None
    y: float | None = None
    diameter: float | None = None
    score: float = 0.0


@dataclass(frozen=True)
class PersonSample:
    t: float
    feet_y: float
    height: float


# ---------------------------------------------------------------------------------------------------------------
# Pure counting
# ---------------------------------------------------------------------------------------------------------------


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _segments(times: np.ndarray, valid: np.ndarray, bridge_s: float) -> list[tuple[int, int]]:
    idx = np.flatnonzero(valid)
    if idx.size == 0:
        return []
    out: list[tuple[int, int]] = []
    start = prev = int(idx[0])
    for k in idx[1:]:
        k = int(k)
        if times[k] - times[prev] > bridge_s:
            out.append((start, prev))
            start = k
        prev = k
    out.append((start, prev))
    return out


def _feet_line(persons: Sequence[PersonSample]) -> tuple[np.ndarray, np.ndarray] | None:
    rows = []
    for person in persons or ():
        t, feet_y = _finite(getattr(person, "t", None)), _finite(getattr(person, "feet_y", None))
        if t is not None and feet_y is not None:
            rows.append((t, feet_y))
    if not rows:
        return None
    rows.sort()
    times = np.array([r[0] for r in rows], dtype=np.float64)
    feet = np.array([r[1] for r in rows], dtype=np.float64)
    if feet.size >= 3:  # running median of 5 against single bad boxes
        padded = np.pad(feet, 2, mode="edge")
        feet = np.array([np.median(padded[i:i + 5]) for i in range(feet.size)])
    return times, feet


def _contact_y(times: np.ndarray, y: np.ndarray, low: int, diameter: float) -> float:
    """Lowest point of the V at sample ``low``: where the falling and rising lines meet (the frame sampling rarely
    catches the exact instant of a contact). Bounded to one diameter below the lowest sample."""
    measured = float(y[low])
    if low < 2 or low + 2 >= y.size:
        return measured
    t1, t2, t3, t4 = (float(times[i]) for i in (low - 2, low - 1, low + 1, low + 2))
    if min(t2 - t1, t4 - t3) <= 0:
        return measured
    fall = (float(y[low - 1]) - float(y[low - 2])) / (t2 - t1)
    rise = (float(y[low + 2]) - float(y[low + 1])) / (t4 - t3)
    if fall <= 0 or rise >= 0:
        return measured
    t_meet = (float(y[low + 1]) - rise * t3 - float(y[low - 1]) + fall * t2) / (fall - rise)
    if not t2 <= t_meet <= t3:
        return measured
    meet = float(y[low - 1]) + fall * (t_meet - t2)
    return min(max(measured, meet), measured + diameter)


def count_touches(samples: Sequence[BallSample], persons: Sequence[PersonSample] = ()) -> dict[str, Any]:
    """Ball trajectory (+ optional feet line) -> touches, ground contacts and streaks. Pure, never raises."""
    try:
        return _count(samples, persons)
    except Exception:
        logger.exception("Touch counting failed")
        return _zero_counts(len(samples) if isinstance(samples, Sequence) else 0, 0)


def _zero_counts(samples: int, seen: int) -> dict[str, Any]:
    return {
        "ball_detected": seen > 0,
        "total_touches": 0,
        "max_streak": 0,
        "streaks": [],
        "ground_contacts": 0,
        "touch_times": [],
        "ground_contact_times": [],
        "samples": int(samples),
        "ball_samples": int(seen),
        "detection_rate": round(seen / samples, 4) if samples else 0.0,
        "ball_diameter_px": None,
    }


def _count(samples: Sequence[BallSample], persons: Sequence[PersonSample]) -> dict[str, Any]:
    rows: list[tuple[float, float, float, float]] = []
    total = 0
    for sample in samples:
        t = _finite(getattr(sample, "t", None))
        if t is None:
            continue
        total += 1
        x, y, d = (_finite(getattr(sample, name, None)) for name in ("x", "y", "diameter"))
        rows.append((t, x if x is not None else math.nan, y if y is not None else math.nan,
                     d if d is not None and d > 0 else math.nan))
    rows.sort(key=lambda r: r[0])
    times = np.array([r[0] for r in rows], dtype=np.float64)
    ys = np.array([r[2] for r in rows], dtype=np.float64)
    ds = np.array([r[3] for r in rows], dtype=np.float64)
    valid = np.isfinite(ys) & np.isfinite(ds)
    seen = int(valid.sum())
    result = _zero_counts(total, seen)
    if seen == 0:
        return result
    diameter = float(np.median(ds[valid]))
    result["ball_diameter_px"] = round(diameter, 2)
    feet = _feet_line(persons)

    contacts: list[tuple[float, bool]] = []  # (time, is_ground)
    lost_gaps: list[tuple[float, float]] = []
    segments = _segments(times, valid, BRIDGE_S)
    for (_, prev_end), (next_start, _) in zip(segments, segments[1:]):
        if times[next_start] - times[prev_end] > DROP_GAP_S:
            lost_gaps.append((float(times[prev_end]), float(times[next_start])))
    for start, end in segments:
        seg = slice(start, end + 1)
        seg_valid = valid[seg]
        if int(seg_valid.sum()) < 3:
            continue
        seg_t = times[seg][seg_valid]
        span = float(seg_t[-1] - seg_t[0])
        steps = np.diff(seg_t)
        dt = float(np.median(steps[steps > 0])) if np.any(steps > 0) else 0.0
        if dt <= 0 or span <= 0:
            continue
        grid = seg_t[0] + dt * np.arange(int(math.floor(span / dt + 1e-6)) + 1)
        raw = np.interp(grid, seg_t, ys[seg][seg_valid])
        d_local = np.interp(grid, seg_t, ds[seg][seg_valid])
        y = np.convolve(np.pad(raw, 1, mode="edge"), [0.25, 0.5, 0.25], mode="valid") if raw.size >= 3 else raw
        peaks, _ = find_peaks(y, prominence=PROMINENCE_DIAMETERS * diameter,
                              distance=max(1, int(round(NMS_SECONDS / dt))))
        window = max(1, int(round(REBOUND_WINDOW_S / dt)))
        for p in peaks:
            t_peak = float(grid[p])
            is_ground = False
            if feet is not None:
                feet_y = float(np.interp(t_peak, feet[0], feet[1]))
                # Unsmoothed positions: smoothing lifts the sharp V of a bounce by about half a diameter.
                low = max(0, p - 1) + int(np.argmax(raw[max(0, p - 1):p + 2]))
                ball_bottom = _contact_y(grid, raw, low, diameter) + float(d_local[low]) / 2.0
                fall = float(raw[low] - np.min(raw[max(0, low - window):low + 1]))
                rise = float(raw[low] - np.min(raw[low:low + window + 1]))
                is_ground = (ball_bottom >= feet_y + GROUND_FEET_MARGIN_DIAMETERS * diameter
                             and rise <= GROUND_REBOUND_RATIO * fall)
            contacts.append((t_peak, is_ground))
    contacts.sort()

    streaks: list[int] = []
    current = 0
    last_touch: float | None = None
    ground_times: list[float] = []
    touch_times: list[float] = []
    for t, is_ground in contacts:
        if is_ground:
            ground_times.append(t)
            if current:
                streaks.append(current)
            current = 0
            last_touch = None
            continue
        if last_touch is not None and (
            t - last_touch > DROP_GAP_S or any(last_touch < a and b < t for a, b in lost_gaps)
        ):
            streaks.append(current)
            current = 0
        current += 1
        last_touch = t
        touch_times.append(t)
    if current:
        streaks.append(current)
    result.update(
        total_touches=len(touch_times),
        max_streak=max(streaks, default=0),
        streaks=streaks,
        ground_contacts=len(ground_times),
        touch_times=[round(t, 3) for t in touch_times],
        ground_contact_times=[round(t, 3) for t in ground_times],
    )
    return result


# ---------------------------------------------------------------------------------------------------------------
# Video -> trajectory
# ---------------------------------------------------------------------------------------------------------------


def _clip_square(cx: float, cy: float, side: float, width: int, height: int) -> tuple[int, int, int]:
    side_i = int(max(8, min(side, width, height)))
    x0 = int(round(min(max(cx - side_i / 2.0, 0), width - side_i)))
    y0 = int(round(min(max(cy - side_i / 2.0, 0), height - side_i)))
    return x0, y0, side_i


def _detect_in(detector: ObjectDetector, frame: np.ndarray, x0: int, y0: int, side_w: int, side_h: int):
    crop = frame[y0:y0 + side_h, x0:x0 + side_w]
    if crop.size == 0:
        return []
    out = []
    for item in detector.detect(crop) or []:
        try:
            label, score, cx, cy, w, h = item
            out.append((str(label), float(score), float(cx) + x0, float(cy) + y0, float(w), float(h)))
        except (TypeError, ValueError):
            continue
    return out


class _ChunkTracker:
    """Greedy single-ball tracker for one chunk of frames (state does not cross chunks)."""

    def __init__(self, detector: ObjectDetector):
        self.detector = detector
        self.last: tuple[float, float, float, float] | None = None  # t, x, y, d
        self.prev: tuple[float, float, float, float] | None = None
        self.diameters: deque[float] = deque(maxlen=15)
        self.person: tuple[float, float, float, float] | None = None  # x0, y0, x1, y1
        self.persons: list[PersonSample] = []
        # The crop size that found the ball last time is tried first (the model's sweet spot differs per video).
        self.crop_scales: list[float] = [CROP_DIAMETERS, RETRY_CROP_DIAMETERS]

    def _ball_size(self) -> float | None:
        return float(np.median(self.diameters)) if self.diameters else None

    def _accept(self, t: float, cand) -> BallSample:
        _, score, x, y, w, h = cand
        d = (w + h) / 2.0
        self.prev, self.last = self.last, (t, x, y, d)
        self.diameters.append(d)
        return BallSample(t=t, x=x, y=y, diameter=d, score=score)

    def _person_zone_ok(self, cand) -> bool:
        if self.person is None:
            return True
        x0, y0, x1, y1 = self.person
        w, h = x1 - x0, y1 - y0
        _, _, x, y, _, _ = cand
        return x0 - 0.6 * w <= x <= x1 + 0.6 * w and y0 - 0.5 * h <= y <= y1 + 0.15 * h

    def _acquire(self, t: float, frame: np.ndarray) -> BallSample:
        height, width = frame.shape[:2]
        found = _detect_in(self.detector, frame, 0, 0, width, height)
        people = [c for c in found if c[0] == PERSON_LABEL and c[1] >= PERSON_SCORE_MIN]
        if people:
            _, _, cx, cy, w, h = max(people, key=lambda c: c[4] * c[5])
            self.person = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
            self.persons.append(PersonSample(t=t, feet_y=cy + h / 2, height=h))
        balls = [c for c in found if c[0] == BALL_LABEL and c[1] >= ACQUIRE_SCORE_MIN and self._person_zone_ok(c)]
        if not balls and self.person is not None:
            x0, y0, x1, y1 = self.person
            w, h = x1 - x0, y1 - y0
            cx0, cy0, side = _clip_square((x0 + x1) / 2, y0 + 0.65 * h, max(w, 0.9 * h), width, height)
            balls = [c for c in _detect_in(self.detector, frame, cx0, cy0, side, side)
                     if c[0] == BALL_LABEL and c[1] >= ACQUIRE_SCORE_MIN and self._person_zone_ok(c)]
        if not balls:
            return BallSample(t=t)
        return self._accept(t, max(balls, key=lambda c: c[1]))

    def step(self, t: float, frame: np.ndarray) -> BallSample:
        size = self._ball_size()
        if self.last is None or size is None or t - self.last[0] > LOST_AFTER_S:
            return self._acquire(t, frame)
        height, width = frame.shape[:2]
        lt, lx, ly, _ = self.last
        px, py = lx, ly
        if self.prev is not None and 0 < lt - self.prev[0] <= LOST_AFTER_S:
            vx = (lx - self.prev[1]) / (lt - self.prev[0])
            vy = (ly - self.prev[2]) / (lt - self.prev[0])
            px, py = lx + vx * (t - lt), ly + vy * (t - lt)
        gate = size * (GATE_BASE_DIAMETERS + GATE_SPEED_DIAMETERS_PER_S * (t - lt))
        for crop_diameters in list(self.crop_scales):
            x0, y0, side = _clip_square(px, py, max(MIN_CROP_SIDE, crop_diameters * size), width, height)
            best = None
            for cand in _detect_in(self.detector, frame, x0, y0, side, side):
                if cand[0] != BALL_LABEL or cand[1] < TRACK_SCORE_MIN:
                    continue
                d = (cand[4] + cand[5]) / 2.0
                if not 0.5 * size <= d <= 2.0 * size:
                    continue
                dist = math.hypot(cand[2] - px, cand[3] - py)
                if dist > gate:
                    continue
                cost = dist / size - 2.0 * cand[1]
                if best is None or cost < best[0]:
                    best = (cost, cand)
            if best is not None:
                if self.crop_scales[0] != crop_diameters:
                    self.crop_scales.remove(crop_diameters)
                    self.crop_scales.insert(0, crop_diameters)
                return self._accept(t, best[1])
        return BallSample(t=t)


class _DetectorPool:
    """One detector per worker thread, created lazily inside that thread; all closed at the end."""

    def __init__(self, factory: DetectorFactory):
        self._factory = factory
        self._local = threading.local()
        self._lock = threading.Lock()
        self._created: list[ObjectDetector] = []

    def get(self) -> ObjectDetector:
        detector = getattr(self._local, "detector", None)
        if detector is None:
            detector = self._factory()
            self._local.detector = detector
            with self._lock:
                self._created.append(detector)
        return detector

    def close(self) -> None:
        with self._lock:
            created, self._created = self._created, []
        for detector in created:
            try:
                detector.close()
            except Exception:  # pragma: no cover - best effort
                logger.debug("Detector close failed", exc_info=True)


def _track_chunk(warmup: list[tuple[float, np.ndarray]], chunk: list[tuple[float, np.ndarray]], pool: _DetectorPool):
    """Track one chunk; the warm-up frames (end of the previous chunk) only seed the tracker state."""
    tracker = _ChunkTracker(pool.get())
    for t, frame in warmup:
        tracker.step(t, frame)
    tracker.persons = []
    samples = [tracker.step(t, frame) for t, frame in chunk]
    return samples, tracker.persons


def _downscale(frame: np.ndarray) -> np.ndarray:
    h, w = frame.shape[:2]
    side = max(h, w)
    if side <= STORE_MAX_SIDE:
        return frame
    scale = STORE_MAX_SIDE / side
    return cv2.resize(frame, (max(1, round(w * scale)), max(1, round(h * scale))), interpolation=cv2.INTER_AREA)


def _chunk_seconds(cap, fps: float, max_seconds: float, n_workers: int) -> float:
    """At most ``CHUNK_SECONDS``, sized so the chunks split evenly over the workers (short clips stay parallel)."""
    frames = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
    duration = min(frames / fps, max_seconds) if frames > 0 and fps > 0 else 0.0
    if duration <= 0:
        return CHUNK_SECONDS
    rounds = max(1, math.ceil(duration / (CHUNK_SECONDS * n_workers)))
    return max(MIN_CHUNK_SECONDS, min(CHUNK_SECONDS, duration / (rounds * n_workers)))


def track_video(
    video_path: str | Path,
    detector_factory: DetectorFactory,
    *,
    max_seconds: float = MAX_SECONDS,
    workers: int | None = None,
) -> dict[str, Any]:
    """Decode ``video_path`` once and track the ball. Raises on unreadable video or detector failure."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        cap.release()
        raise ValueError("unreadable video")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    if not 0 < fps <= 1000:
        fps = 30.0
    stride = max(1, int(fps // MIN_SAMPLE_HZ))
    n_workers = max(1, min(MAX_WORKERS, workers or (os.cpu_count() or 1)))
    chunk_len = max(1, round(_chunk_seconds(cap, fps, max_seconds, n_workers) * fps / stride))
    warmup_len = max(0, round(WARMUP_SECONDS * fps / stride))
    detectors = _DetectorPool(detector_factory)
    samples: list[BallSample] = []
    persons: list[PersonSample] = []
    frames_read = 0
    truncated = False
    try:
        pending: deque[Future] = deque()
        with ThreadPoolExecutor(max_workers=n_workers) as executor:
            def collect(limit: int) -> None:
                while len(pending) > limit:
                    chunk_samples, chunk_persons = pending.popleft().result()
                    samples.extend(chunk_samples)
                    persons.extend(chunk_persons)

            chunk: list[tuple[float, np.ndarray]] = []
            warmup: list[tuple[float, np.ndarray]] = []
            index = 0
            try:
                while True:
                    t = index / fps
                    if t > max_seconds:
                        truncated = bool(cap.grab())
                        break
                    if index % stride:
                        if not cap.grab():
                            break
                        index += 1
                        continue
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        break
                    index += 1
                    chunk.append((t, _downscale(frame)))
                    if len(chunk) >= chunk_len:
                        pending.append(executor.submit(_track_chunk, warmup, chunk, detectors))
                        warmup = chunk[len(chunk) - warmup_len:] if warmup_len else []
                        chunk = []
                        collect(n_workers)
                if chunk:
                    pending.append(executor.submit(_track_chunk, warmup, chunk, detectors))
                collect(0)
            finally:
                for future in pending:
                    future.cancel()
            frames_read = index
    finally:
        cap.release()
        detectors.close()
    return {
        "samples": samples,
        "persons": persons,
        "fps": fps,
        "sample_hz": round(fps / stride, 2),
        "frames_read": frames_read,
        "analyzed_seconds": round(frames_read / fps, 2) if fps else 0.0,
        "truncated": truncated,
    }


def analyze_ball_video(
    video_path: str | Path,
    detector_factory: DetectorFactory,
    *,
    max_seconds: float = MAX_SECONDS,
    workers: int | None = None,
) -> dict[str, Any]:
    """Video -> ``analysis["ball"]`` block (plus diagnostics). Raises only when the video/detector fails."""
    tracked = track_video(video_path, detector_factory, max_seconds=max_seconds, workers=workers)
    counts = count_touches(tracked["samples"], tracked["persons"])
    return {
        **counts,
        "ball_frames": counts["ball_samples"],
        "frames_analyzed": tracked["frames_read"],
        "analyzed_seconds": tracked["analyzed_seconds"],
        "sample_hz": tracked["sample_hz"],
        "truncated": tracked["truncated"],
        "detector": DETECTOR_NAME,
    }

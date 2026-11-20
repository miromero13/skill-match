"""Tolerant, view-robust comparison of two pose signatures.

Pipeline: parse -> resample to the common rate -> trim idle lead-in/out -> joint weights from the
reference motion -> masked angular cost matrix -> slope-constrained subsequence DTW (tempo ratio
0.5x-2x; the longer sequence may contain repeated cycles) -> best of normal and mirrored user ->
mean angular distance (degrees) -> generous tolerance curve and anti-false-pass factors.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from app.skill_validation.pose import (
    FEATURE_COUNT,
    FEATURE_NAMES,
    MIRROR_INDEX,
    PRIOR_WEIGHTS,
    SAMPLE_FPS,
    VISIBILITY_THRESHOLD,
)

# Default tolerance: full marks up to D_FULL degrees of joint-angle distance, zero from D_ZERO. Measured on
# 18 real juggling clips (MediaPipe full): the same clip mirrored / perspective-warped / rotated+zoomed /
# 0.6x-1.6x tempo lands at 2-11 deg; the same motion by different people and cameras at 6-21 deg
# (median 15, p90 18); squats / jumping jacks / arm waves against real juggling at 25-39 deg.
DEFAULT_D_FULL = 17.0
DEFAULT_D_ZERO = 28.0
MIN_TOLERANCE_GAP = 8.0
ABS_MIN_D_FULL, ABS_MAX_D_FULL = 4.0, 40.0
ABS_MIN_D_ZERO, ABS_MAX_D_ZERO = 12.0, 70.0

MIN_POSE_FRAMES = 8
MAX_COMPARE_FRAMES = 600
MAX_ANGLE_DIFF = 90.0
MISSING_JOINT_COST = 30.0
TIME_POWER = 2.0  # power mean along the path: a phase done wrong is not hidden by shared rest phases
MIN_JOINT_VALID_FRACTION = 0.3
MOVING_REFERENCE_RANGE = 15.0  # weighted mean range (deg) above which the reference "moves"
MOTION_RATIO_ZERO, MOTION_RATIO_FULL = 0.15, 0.45  # user/reference motion range (real pairs: 0.4-1.9)
EXCESS_RATIO_FULL, EXCESS_RATIO_ZERO = 2.5, 6.0
COVERAGE_FULL = 0.6
CYCLE_EXPLAIN_RATIO, CYCLE_EXPLAIN_MARGIN = 1.3, 4.0  # a reference stretch "also done" by the user
DETECTED_RATIO_FULL = 0.3


@dataclass
class PoseSequence:
    angles: np.ndarray  # (n, F) degrees, NaN when unknown
    valid: np.ndarray  # (n, F) bool
    fps: float
    detected_ratio: float


def parse_pose(pose: Any) -> PoseSequence | None:
    """Detected frames of a stored pose block, or ``None`` when it is not a usable signature."""
    if not isinstance(pose, dict):
        return None
    if list(pose.get("features") or FEATURE_NAMES) != FEATURE_NAMES:
        return None
    signature = pose.get("signature")
    visibility = pose.get("visibility")
    if not isinstance(signature, list):
        return None
    if not isinstance(visibility, list) or len(visibility) != len(signature):
        visibility = [None] * len(signature)
    angle_rows: list[list[float]] = []
    vis_rows: list[list[float]] = []
    for row, vis in zip(signature, visibility):
        if not isinstance(row, list) or len(row) != FEATURE_COUNT:
            continue
        values = [float(v) if isinstance(v, (int, float)) and math.isfinite(v) else math.nan for v in row]
        if isinstance(vis, list) and len(vis) == FEATURE_COUNT:
            vis_values = [float(v) if isinstance(v, (int, float)) and math.isfinite(v) else 0.0 for v in vis]
        else:
            vis_values = [1.0] * FEATURE_COUNT
        angle_rows.append(values)
        vis_rows.append(vis_values)
    if not angle_rows:
        return None
    angles = np.array(angle_rows, dtype=np.float64)
    vis_arr = np.array(vis_rows, dtype=np.float64)
    valid = np.isfinite(angles) & (vis_arr >= VISIBILITY_THRESHOLD)
    fps = pose.get("fps")
    fps = float(fps) if isinstance(fps, (int, float)) and math.isfinite(fps) and 0.5 <= fps <= 240 else SAMPLE_FPS
    ratio = pose.get("detected_ratio")
    ratio = float(ratio) if isinstance(ratio, (int, float)) and math.isfinite(ratio) else 1.0
    seq = PoseSequence(np.where(valid, angles, np.nan), valid, fps, max(0.0, min(1.0, ratio)))
    return _normalize_rate(seq)


def _normalize_rate(seq: PoseSequence) -> PoseSequence:
    """Resample to SAMPLE_FPS when off by >15% and cap the length used by the DTW."""
    angles, valid, fps = seq.angles, seq.valid, seq.fps
    n = len(angles)
    if n >= 2 and abs(fps - SAMPLE_FPS) / SAMPLE_FPS > 0.15:
        target_n = max(2, int(round(n * SAMPLE_FPS / fps)))
        src = np.linspace(0, n - 1, target_n)
        idx = np.clip(np.round(src).astype(int), 0, n - 1)
        angles, valid, fps = angles[idx], valid[idx], SAMPLE_FPS
        n = target_n
    if n > MAX_COMPARE_FRAMES:
        idx = np.linspace(0, n - 1, MAX_COMPARE_FRAMES).round().astype(int)
        fps = fps * MAX_COMPARE_FRAMES / n
        angles, valid = angles[idx], valid[idx]
    return PoseSequence(angles, valid, fps, seq.detected_ratio)


def pose_fingerprint(pose: Any) -> str | None:
    """Stable short id of a reference signature (detects a replaced reference after training)."""
    if not isinstance(pose, dict) or not isinstance(pose.get("signature"), list):
        return None
    try:
        raw = json.dumps(pose.get("signature"), separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError):
        return None
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _motion_speed(seq: PoseSequence) -> np.ndarray:
    diffs = np.abs(np.diff(seq.angles, axis=0))
    both = seq.valid[1:] & seq.valid[:-1]
    diffs = np.where(both, np.nan_to_num(diffs), 0.0)
    counts = both.sum(axis=1)
    speed = np.where(counts > 0, diffs.sum(axis=1) / np.maximum(counts, 1), 0.0)
    if len(speed) >= 5:
        speed = np.convolve(speed, np.ones(5) / 5.0, mode="same")
    return speed


def trim_idle(seq: PoseSequence) -> PoseSequence:
    """Drop the idle lead-in/out (standing before starting, walking to stop the camera)."""
    n = len(seq.angles)
    if n < 10:
        return seq
    speed = _motion_speed(seq)
    threshold = max(1.0, 0.2 * float(np.percentile(speed, 90)))
    active = np.flatnonzero(speed > threshold)
    if len(active) < 3:
        return seq
    pad = 3
    start = max(0, int(active[0]) - pad)
    end = min(n, int(active[-1]) + 2 + pad)
    if end - start < MIN_POSE_FRAMES:
        return seq
    return PoseSequence(seq.angles[start:end], seq.valid[start:end], seq.fps, seq.detected_ratio)


def _ranges(seq: PoseSequence) -> tuple[np.ndarray, np.ndarray]:
    """Per-feature range of motion (p95-p5) and fraction of frames where it is visible."""
    frac = seq.valid.mean(axis=0) if len(seq.valid) else np.zeros(FEATURE_COUNT)
    ranges = np.zeros(FEATURE_COUNT)
    for f in range(FEATURE_COUNT):
        col = seq.angles[seq.valid[:, f], f]
        if len(col) >= 3:
            ranges[f] = float(np.percentile(col, 95) - np.percentile(col, 5))
    return ranges, frac


def joint_weights(reference: PoseSequence, user: PoseSequence | None = None) -> np.ndarray:
    """Joints that move (in the reference or in the user) matter most; still joints keep a posture weight.

    Counting the user's motion too means moving joints the reference keeps still is not ignored.
    """
    ranges, frac = _ranges(reference)
    if user is not None:
        user_ranges, _ = _ranges(user)
        ranges = np.maximum(ranges, user_ranges)
    scale = max(float(ranges.max()) if len(ranges) else 0.0, 20.0)
    weights = PRIOR_WEIGHTS * (0.25 + 0.75 * ranges / scale) * frac
    weights[frac < MIN_JOINT_VALID_FRACTION] = 0.0
    return weights


def mirror(seq: PoseSequence) -> PoseSequence:
    return PoseSequence(seq.angles[:, MIRROR_INDEX], seq.valid[:, MIRROR_INDEX], seq.fps, seq.detected_ratio)


def cost_matrix(
    rows: PoseSequence, cols: PoseSequence, weights: np.ndarray, reference_is_rows: bool = True
) -> np.ndarray:
    """Weighted mean absolute angle difference over the joints visible in both frames.

    Joints visible in the reference frame but not in the user frame cost MISSING_JOINT_COST (filming only
    half the body must not be a shortcut); joints the reference itself does not show cost nothing.
    """
    n, m = len(rows.angles), len(cols.angles)
    out = np.empty((n, m))
    ra = np.nan_to_num(rows.angles)
    ca = np.nan_to_num(cols.angles)
    rv = rows.valid.astype(np.float64)
    cv = cols.valid.astype(np.float64)
    ref_w = (rv * weights[None, :]).sum(axis=1)[:, None] if reference_is_rows else (cv * weights[None, :]).sum(axis=1)[None, :]
    chunk = max(1, 2_000_000 // max(1, m * FEATURE_COUNT))
    for start in range(0, n, chunk):
        end = min(n, start + chunk)
        diff = np.minimum(np.abs(ra[start:end, None, :] - ca[None, :, :]), MAX_ANGLE_DIFF)
        w = weights[None, None, :] * rv[start:end, None, :] * cv[None, :, :]
        wsum = w.sum(axis=2)
        with np.errstate(all="ignore"):
            # Root mean square over joints: one limb doing something else weighs more than uniform jitter.
            mean = np.where(
                wsum > 0, np.sqrt((w * diff * diff).sum(axis=2) / np.where(wsum > 0, wsum, 1.0)), MISSING_JOINT_COST
            )
        block_ref_w = ref_w[start:end] if reference_is_rows else ref_w
        with np.errstate(all="ignore"):
            frac = np.where(block_ref_w > 0, wsum / np.where(block_ref_w > 0, block_ref_w, 1.0), 0.0)
        frac = np.clip(frac, 0.0, 1.0)
        out[start:end] = frac * mean + (1.0 - frac) * MISSING_JOINT_COST
    return out


def subsequence_dtw(cost: np.ndarray) -> tuple[float, int, int]:
    """Every row matched once, columns open at both ends; slope limited to [0.5, 2].

    Steps (1,1), (1,2) and (2,1) with weight 1 per row, so the accumulated cost divided by the row count
    is the mean cost along the path. Returns ``(mean cost, first column, last column)``.
    """
    n, m = cost.shape
    inf = math.inf
    prev2 = np.full(m, inf)
    prev2_start = np.zeros(m, dtype=np.int64)
    prev = cost[0].copy()
    prev_start = np.arange(m, dtype=np.int64)
    if n == 1:
        j = int(np.argmin(prev))
        return float(prev[j]), j, j
    prev_row_cost = cost[0]
    for i in range(1, n):
        row = cost[i]
        best = np.full(m, inf)
        start = np.zeros(m, dtype=np.int64)
        # (1,1)
        cand = np.full(m, inf)
        cand[1:] = prev[:-1] + row[1:]
        take = cand < best
        best[take] = cand[take]
        start[1:][take[1:]] = prev_start[:-1][take[1:]]
        # (1,2): one row, two columns averaged
        cand = np.full(m, inf)
        cand[2:] = prev[:-2] + 0.5 * (row[1:-1] + row[2:])
        take = cand < best
        best[take] = cand[take]
        start[2:][take[2:]] = prev_start[:-2][take[2:]]
        # (2,1): two rows, one column
        if i >= 2:
            cand = np.full(m, inf)
            cand[1:] = prev2[:-1] + prev_row_cost[1:] + row[1:]
            take = cand < best
            best[take] = cand[take]
            start[1:][take[1:]] = prev2_start[:-1][take[1:]]
        elif i == 1:
            # (2,1) starting at the virtual row -1 (open begin): rows 0 and 1 on the same column.
            cand = prev_row_cost + row
            take = cand < best
            best[take] = cand[take]
            start[take] = np.arange(m)[take]
        prev2, prev2_start = prev, prev_start
        prev, prev_start = best, start
        prev_row_cost = row
    j = int(np.argmin(prev))
    if not math.isfinite(prev[j]):
        return math.inf, 0, m - 1
    return float(prev[j]) / n, int(prev_start[j]), j


def tolerance_score(distance: float, d_full: float, d_zero: float) -> float:
    """100 up to d_full, 0 from d_zero, smooth (half cosine) in between."""
    if not math.isfinite(distance):
        return 0.0
    if distance <= d_full:
        return 100.0
    if distance >= d_zero:
        return 0.0
    t = (distance - d_full) / (d_zero - d_full)
    return 100.0 * 0.5 * (1.0 + math.cos(math.pi * t))


def sanitize_tolerance(d_full: Any, d_zero: Any) -> tuple[float, float] | None:
    try:
        f, z = float(d_full), float(d_zero)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(f) and math.isfinite(z)):
        return None
    f = min(max(f, ABS_MIN_D_FULL), ABS_MAX_D_FULL)
    z = min(max(z, ABS_MIN_D_ZERO, f + MIN_TOLERANCE_GAP), ABS_MAX_D_ZERO)
    return f, z


@dataclass
class Comparison:
    ok: bool
    distance: float = math.inf
    mirrored: bool = False
    coverage: float = 0.0
    motion_ratio: float = 1.0
    motion_factor: float = 1.0
    coverage_factor: float = 1.0
    presence_factor: float = 1.0
    user_frames: int = 0
    reference_frames: int = 0
    reason: str | None = None  # "user" (not enough pose) / "reference"

    def score(self, d_full: float, d_zero: float) -> float:
        if not self.ok:
            return 0.0
        base = tolerance_score(self.distance, d_full, d_zero)
        return base * self.motion_factor * self.coverage_factor * self.presence_factor

    def detail(self) -> dict[str, Any]:
        return {
            "distance_deg": round(self.distance, 2) if math.isfinite(self.distance) else None,
            "mirrored": self.mirrored,
            "coverage": round(self.coverage, 3),
            "motion_ratio": round(self.motion_ratio, 3),
            "motion_factor": round(self.motion_factor, 3),
            "coverage_factor": round(self.coverage_factor, 3),
            "presence_factor": round(self.presence_factor, 3),
            "user_frames": self.user_frames,
            "reference_frames": self.reference_frames,
        }


def _dtw_distance(rows: PoseSequence, cols: PoseSequence, weights: np.ndarray, reference_is_rows: bool):
    mean_power, j0, j1 = subsequence_dtw(cost_matrix(rows, cols, weights, reference_is_rows) ** TIME_POWER)
    return mean_power ** (1.0 / TIME_POWER), j0, j1


def _slice(seq: PoseSequence, start: int, end: int) -> PoseSequence:
    return PoseSequence(seq.angles[start:end], seq.valid[start:end], seq.fps, seq.detected_ratio)


def _match(reference: PoseSequence, user: PoseSequence, weights: np.ndarray) -> tuple[float, float]:
    """(distance, coverage of the reference).

    A user longer than the reference is searched for its best matching stretch (coverage 1). A shorter
    user is matched inside the reference; the rest of the reference still counts as covered when the
    user's motion also explains it (a cyclic reference, e.g. 60 s of the same juggling cycle), so only
    a genuinely partial replication of a sequence loses coverage.
    """
    n, m = len(reference.angles), len(user.angles)
    if m >= n:
        distance, _, _ = _dtw_distance(reference, user, weights, True)
        return distance, 1.0
    distance, j0, j1 = _dtw_distance(user, reference, weights, False)
    if not math.isfinite(distance):
        return distance, 0.0
    covered = np.zeros(n, dtype=bool)
    covered[j0:j1 + 1] = True
    threshold = max(distance * CYCLE_EXPLAIN_RATIO, distance + CYCLE_EXPLAIN_MARGIN)
    bounds = list(range(0, n, m)) + [n]
    if len(bounds) > 2 and bounds[-1] - bounds[-2] < m // 2:
        bounds.pop(-2)  # merge a short tail into the previous chunk (still <= 2m rows: DTW-feasible)
    for start, end in zip(bounds[:-1], bounds[1:]):
        if covered[start:end].all():
            continue
        chunk_distance, _, _ = _dtw_distance(_slice(reference, start, end), user, weights, True)
        if chunk_distance <= threshold:
            covered[start:end] = True
    return distance, float(covered.mean())


def compare_sequences(reference: PoseSequence, user: PoseSequence) -> Comparison:
    ref = trim_idle(reference)
    if len(ref.angles) < MIN_POSE_FRAMES:
        return Comparison(ok=False, reason="reference", reference_frames=len(ref.angles))
    usr = trim_idle(user)
    if len(usr.angles) < MIN_POSE_FRAMES:
        return Comparison(ok=False, reason="user", user_frames=len(usr.angles), reference_frames=len(ref.angles))
    if float(joint_weights(ref).sum()) <= 0:
        return Comparison(ok=False, reason="reference", reference_frames=len(ref.angles))

    best: tuple[float, float, bool, PoseSequence, np.ndarray] | None = None
    for mirrored, candidate in ((False, usr), (True, mirror(usr))):
        weights = joint_weights(ref, candidate)
        distance, coverage = _match(ref, candidate, weights)
        if best is None or distance < best[0]:
            best = (distance, coverage, mirrored, candidate, weights)
    assert best is not None
    distance, coverage, mirrored, chosen, _ = best
    weights = joint_weights(ref)

    ref_ranges, _ = _ranges(ref)
    usr_ranges, _ = _ranges(chosen)
    wsum = float(weights.sum())
    ref_motion = float((weights * ref_ranges).sum()) / wsum
    usr_motion = float((weights * usr_ranges).sum()) / wsum
    motion_ratio = usr_motion / ref_motion if ref_motion > 1e-6 else 1.0
    motion_factor = 1.0
    if ref_motion >= MOVING_REFERENCE_RANGE:  # a (nearly) static user must not replicate a moving reference
        low = (motion_ratio - MOTION_RATIO_ZERO) / (MOTION_RATIO_FULL - MOTION_RATIO_ZERO)
        motion_factor = min(motion_factor, max(0.0, low))
    if usr_motion >= MOVING_REFERENCE_RANGE:  # nor a much more agitated user a calm/static reference
        excess = usr_motion / max(ref_motion, 1e-6)
        high = (EXCESS_RATIO_ZERO - excess) / (EXCESS_RATIO_ZERO - EXCESS_RATIO_FULL)
        motion_factor = min(motion_factor, max(0.0, min(1.0, high)))
    motion_factor = min(1.0, max(0.0, motion_factor))
    return Comparison(
        ok=math.isfinite(distance),
        distance=distance,
        mirrored=mirrored,
        coverage=coverage,
        motion_ratio=motion_ratio,
        motion_factor=motion_factor,
        coverage_factor=min(1.0, coverage / COVERAGE_FULL),
        presence_factor=min(1.0, user.detected_ratio / DETECTED_RATIO_FULL),
        user_frames=len(usr.angles),
        reference_frames=len(ref.angles),
        reason=None if math.isfinite(distance) else "user",
    )

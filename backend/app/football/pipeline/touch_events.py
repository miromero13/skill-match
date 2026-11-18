from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import savgol_filter

from app.football.config import TouchEventsConfig, load_football_config
from app.football.pipeline.ball_tracker import BallTrack


@dataclass
class TouchCandidate:
    t_ms: int
    frame_idx: int
    x: float
    y: float
    height_diameters: float
    velocity_delta_diameters_per_s: float
    confidence: float
    is_ground_bounce: bool = False


def detect_video_touch_events(
    track: BallTrack,
    config: TouchEventsConfig | None = None,
    min_separation_ms: int = 240,
) -> list[TouchCandidate]:
    """
    Pure pipeline step (`touch_events`):
    `BallTrack` -> list of `TouchCandidate`.
    Smooths normalized ball height (`height_diameters`) with Savitzky-Golay and
    identifies local height minima where vertical velocity transitions from downward
    (`< 0`) to upward (`> 0`) with a velocity change exceeding `min_velocity_delta`.
    """
    cfg = config or load_football_config().touch_events
    pts = track.points
    if len(pts) < 5:
        return []

    heights = np.array([pt.height_diameters for pt in pts], dtype=np.float64)
    window = min(cfg.savgol_window_length, len(heights))
    if window % 2 == 0:
        window = max(3, window - 1)
    poly = min(cfg.savgol_polyorder, window - 1)

    smoothed_h = (
        savgol_filter(heights, window_length=window, polyorder=poly)
        if window >= 3
        else heights
    )

    dt_s = 1.0 / max(1.0, track.fps)
    # Forward/backward finite differences around each frame i to capture sharp rebound
    raw_candidates: list[TouchCandidate] = []
    half_span = max(1, min(3, round(track.fps * 0.08)))

    for i in range(half_span, len(pts) - half_span):
        h_curr = float(smoothed_h[i])
        # Touch occurs in the lower zone (within 0.85 ball diameters of foot baseline)
        if h_curr > 0.85:
            continue
        # Must be a local minimum in the local window [i - half_span, i + half_span]
        local_slice = smoothed_h[i - half_span : i + half_span + 1]
        if h_curr > float(np.min(local_slice)) + 1e-6:
            continue

        # Velocity before frame i (descending -> negative) and after frame i (ascending -> positive)
        v_before = float(smoothed_h[i] - smoothed_h[i - half_span]) / (
            half_span * dt_s
        )
        v_after = float(smoothed_h[i + half_span] - smoothed_h[i]) / (
            half_span * dt_s
        )

        if v_before < -0.05 and v_after > 0.05:
            velocity_delta = v_after - v_before
            if cfg.min_velocity_delta <= velocity_delta <= 50.0 and not pts[i].interpolated:
                pt = pts[i]
                conf = min(
                    1.0,
                    float(pt.confidence)
                    * min(1.0, velocity_delta / (cfg.min_velocity_delta * 2.5)),
                )
                raw_candidates.append(
                    TouchCandidate(
                        t_ms=pt.t_ms,
                        frame_idx=pt.frame_idx,
                        x=pt.x,
                        y=pt.y,
                        height_diameters=max(0.0, h_curr),
                        velocity_delta_diameters_per_s=velocity_delta,
                        confidence=max(0.5, conf),
                        is_ground_bounce=pt.is_ground_level,
                    )
                )

    # Non-maximum suppression within `min_separation_ms` (keep strongest rebound delta)
    filtered: list[TouchCandidate] = []
    for cand in raw_candidates:
        if not filtered:
            filtered.append(cand)
            continue
        prev = filtered[-1]
        if (cand.t_ms - prev.t_ms) < min_separation_ms:
            if (
                cand.velocity_delta_diameters_per_s
                > prev.velocity_delta_diameters_per_s
            ):
                filtered[-1] = cand
        else:
            filtered.append(cand)

    ground_bounces = _detect_ground_bounces(pts, min_separation_ms=min_separation_ms)

    # Drop foot-touch candidates too close to a ground bounce: the ball crossing
    # foot level while falling into or rebounding out of the bounce is part of
    # that same physical event, not a separate touch.
    bounce_exclusion_ms = 350
    foot_touches = [
        cand
        for cand in filtered
        if all(abs(cand.t_ms - b.t_ms) > bounce_exclusion_ms for b in ground_bounces)
    ]

    combined = foot_touches + ground_bounces
    combined.sort(key=lambda c: c.t_ms)
    return combined


def _detect_ground_bounces(
    pts: list,
    min_separation_ms: int,
) -> list[TouchCandidate]:
    """
    Ground contacts flatten `height_diameters` near zero over several frames
    (unlike a sharp foot-touch rebound), so they are detected directly from
    `is_ground_level` runs rather than from the velocity-sign-change filter
    used for foot touches. Each contiguous run of ground-level, non-interpolated
    points yields one bounce centered on its lowest (deepest) point.
    """
    bounces: list[TouchCandidate] = []
    run: list = []

    def flush_run() -> None:
        if not run:
            return
        deepest = max(run, key=lambda pt: pt.y)
        bounces.append(
            TouchCandidate(
                t_ms=deepest.t_ms,
                frame_idx=deepest.frame_idx,
                x=deepest.x,
                y=deepest.y,
                height_diameters=0.0,
                velocity_delta_diameters_per_s=0.0,
                confidence=max(0.5, float(deepest.confidence)),
                is_ground_bounce=True,
            )
        )

    for pt in pts:
        if pt.is_ground_level and not pt.interpolated:
            run.append(pt)
            continue
        flush_run()
        run = []
    flush_run()

    # Merge bounce centers closer than min_separation_ms (same physical bounce)
    bounces.sort(key=lambda c: c.t_ms)
    merged: list[TouchCandidate] = []
    for cand in bounces:
        if merged and (cand.t_ms - merged[-1].t_ms) < min_separation_ms:
            continue
        merged.append(cand)
    return merged

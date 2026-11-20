from __future__ import annotations

from typing import Any

import numpy as np

from app.football.pipeline.ball_tracker import BallTrack
from app.football.pipeline.challenge_engine import (
    ChallengeEvaluationSummary,
    _compute_touch_peak_heights,
)
from app.football.pipeline.fusion import FusedTouchEvent, FusionSummary

# A pause longer than this between two touches means the ball was lost (a drop).
DROP_GAP_S = 2.2


def _split_valid_events(
    fusion: FusionSummary,
) -> tuple[list[FusedTouchEvent], list[FusedTouchEvent]]:
    """Return `(touches, all_valid_events)`; ground bounces are only in the second list."""
    all_valid_events = sorted(
        [
            ev
            for ev in fusion.events
            if ev.estado
            in (
                {"confirmed", "video_only", "audio_only"}
                if fusion.coherence >= 0.50
                else {"confirmed", "video_only"}
            )
        ],
        key=lambda e: e.t_ms,
    )
    # Ground bounces (ball hit the floor, not the player) break the juggling
    # streak but are not themselves a valid touch, so they are excluded from
    # total_touches/touch_times_ms while still acting as a streak boundary.
    valid_events = [ev for ev in all_valid_events if not ev.is_ground_bounce]
    return valid_events, all_valid_events


def _streak_break(
    t_curr: int, t_next: int, all_valid_events: list[FusedTouchEvent]
) -> tuple[float, bool]:
    """`(gap_s, breaks)`: a streak breaks on a > 2.2 s gap or a ground bounce in between."""
    dt_s = (t_next - t_curr) / 1000.0
    bounce_between = any(
        t_curr < ev.t_ms < t_next for ev in all_valid_events if ev.is_ground_bounce
    )
    return dt_s, dt_s > DROP_GAP_S or bounce_between


def compute_touch_streaks(fusion: FusionSummary) -> list[int]:
    """
    Lengths of every run of consecutive touches without a drop, in time order
    (same rule as `extract_session_features`: reset on a ground bounce or a
    > 2.2 s gap). `max(streaks)` equals the feature `max_streak`.
    """
    valid_events, all_valid_events = _split_valid_events(fusion)
    if not valid_events:
        return []
    streaks: list[int] = []
    current = 1
    for idx in range(len(valid_events) - 1):
        _, breaks = _streak_break(
            valid_events[idx].t_ms, valid_events[idx + 1].t_ms, all_valid_events
        )
        if breaks:
            streaks.append(current)
            current = 1
        else:
            current += 1
    streaks.append(current)
    return streaks


def extract_session_features(
    track: BallTrack | None,
    fusion: FusionSummary,
    challenge_eval: ChallengeEvaluationSummary | None = None,
    session_duration_s: float | None = None,
) -> dict[str, Any]:
    """
    Pure pipeline step (`features`):
    Consolidates tracking, audio-video fusion, and dynamic challenge outputs into
    the canonical feature dictionary required by `scoring` and `fraud`.
    """
    valid_events, all_valid_events = _split_valid_events(fusion)
    touch_times_ms = [ev.t_ms for ev in valid_events]
    total_touches = len(touch_times_ms)
    ground_bounce_count = sum(1 for ev in all_valid_events if ev.is_ground_bounce)

    # Compute intervals, drops (> 2.2 s gap between touches, or a ground bounce
    # between them), and max streak of consecutive touches without a drop.
    intervals_s: list[float] = []
    drops = ground_bounce_count
    for idx in range(len(valid_events) - 1):
        dt_s, _ = _streak_break(
            valid_events[idx].t_ms, valid_events[idx + 1].t_ms, all_valid_events
        )
        intervals_s.append(dt_s)
        if dt_s > DROP_GAP_S:
            drops += 1
    max_streak = max(compute_touch_streaks(fusion), default=0)

    # Regularity: standard deviation of non-drop inter-touch intervals (seconds)
    active_intervals = [dt for dt in intervals_s if dt <= DROP_GAP_S]
    interval_std_s = (
        float(np.std(active_intervals)) if len(active_intervals) >= 2 else 0.0
    )
    regularity_score = round(1.0 / (1.0 + 3.0 * interval_std_s), 4)

    # Duration in seconds
    if session_duration_s and session_duration_s > 0:
        duration_s = float(session_duration_s)
    elif track and track.points and track.fps > 0:
        duration_s = len(track.points) / float(track.fps)
    elif touch_times_ms:
        duration_s = max(1.0, (touch_times_ms[-1] - touch_times_ms[0] + 1000) / 1000.0)
    else:
        duration_s = 1.0

    touches_per_minute = round((total_touches * 60.0) / max(1.0, duration_s), 2)

    # Ball height metrics (in ball diameters) and horizontal displacement
    peak_heights = _compute_touch_peak_heights(touch_times_ms, track)
    mean_height_diameters = (
        round(float(np.mean(peak_heights)), 3) if peak_heights else 0.0
    )
    height_std_diameters = (
        round(float(np.std(peak_heights)), 3) if len(peak_heights) >= 2 else 0.0
    )

    horizontal_std_diameters = 0.0
    if track and track.points:
        ball_diam_px = max(2.0, 2.0 * track.median_radius_px)
        x_diam = np.array(
            [pt.x / ball_diam_px for pt in track.points], dtype=np.float64
        )
        horizontal_std_diameters = round(float(np.std(x_diam)), 3)

    mean_compliance = (
        challenge_eval.mean_compliance if challenge_eval is not None else 1.0
    )
    mean_reaction_latency_ms = (
        challenge_eval.mean_reaction_latency_ms
        if challenge_eval is not None
        else None
    )
    plan_coherent = (
        challenge_eval.plan_coherent if challenge_eval is not None else True
    )

    total_raw_events = len(fusion.events)
    confirmation_rate = (
        round(fusion.confirmed_count / float(total_raw_events), 4)
        if total_raw_events > 0
        else 0.0
    )

    return {
        "total_touches": total_touches,
        "max_streak": max_streak,
        "ground_bounce_count": ground_bounce_count,
        "touches_per_minute": touches_per_minute,
        "interval_std_s": round(interval_std_s, 4),
        "regularity_score": regularity_score,
        "mean_height_diameters": mean_height_diameters,
        "height_std_diameters": height_std_diameters,
        "horizontal_displacement_diameters": horizontal_std_diameters,
        "drops_count": drops,
        "mean_challenge_compliance": round(mean_compliance, 4),
        "mean_reaction_latency_ms": mean_reaction_latency_ms,
        "plan_coherent": plan_coherent,
        "confirmation_rate": confirmation_rate,
        "av_coherence": fusion.coherence,
        "av_drift_ms_per_min": fusion.drift_ms_per_min,
        "duration_s": round(duration_s, 2),
    }

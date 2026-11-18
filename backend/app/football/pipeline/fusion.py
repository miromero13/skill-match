from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.football.config import FusionConfig, load_football_config
from app.football.pipeline.audio_events import AudioImpactEvent
from app.football.pipeline.touch_events import TouchCandidate


@dataclass
class FusedTouchEvent:
    t_ms: int
    estado: str  # "confirmed" | "video_only" | "audio_only"
    confianza: float
    video_t_ms: int | None = None
    audio_t_ms: int | None = None
    offset_ms: int | None = None
    is_ground_bounce: bool = False


@dataclass
class FusionSummary:
    events: list[FusedTouchEvent] = field(default_factory=list)
    confirmed_count: int = 0
    video_only_count: int = 0
    audio_only_count: int = 0
    effective_touch_count: int = 0
    coherence: float = 0.0
    drift_ms_per_min: float = 0.0
    estimated_calibration_offset_ms: int = 0


def estimate_calibration_offset_ms(
    video_events: list[TouchCandidate],
    audio_events: list[AudioImpactEvent],
    calibration_touch_ms: int | None = None,
    max_calibration_offset_ms: int = 120,
) -> int:
    """
    Estimate initial audio-video clock offset (`audio_t_ms - video_t_ms`).
    If `calibration_touch_ms` is provided or if early video/audio events align within
    `max_calibration_offset_ms`, returns the median offset so constant hardware latency
    is compensated before ±70 ms fusion.
    """
    if not video_events or not audio_events:
        return 0

    if calibration_touch_ms is not None:
        nearest_v = min(
            video_events, key=lambda v: abs(v.t_ms - calibration_touch_ms)
        )
        nearest_a = min(
            audio_events, key=lambda a: abs(a.t_ms - calibration_touch_ms)
        )
        diff = nearest_a.t_ms - nearest_v.t_ms
        if abs(diff) <= max_calibration_offset_ms:
            return int(diff)

    # Fallback: check median nearest difference on the first up to 3 touches
    candidate_diffs: list[int] = []
    for v_ev in video_events[:3]:
        nearest_a = min(audio_events, key=lambda a: abs(a.t_ms - v_ev.t_ms))
        diff = nearest_a.t_ms - v_ev.t_ms
        if abs(diff) <= 120:
            candidate_diffs.append(diff)

    if candidate_diffs:
        return round(float(np.median(candidate_diffs)))
    return 0


def fuse_audio_video_events(
    video_events: list[TouchCandidate],
    audio_events: list[AudioImpactEvent],
    calibration_touch_ms: int | None = None,
    config: FusionConfig | None = None,
) -> FusionSummary:
    """
    Pure pipeline step (`fusion`):
    Pairs `video_events` and `audio_events` after compensating `calibration_offset_ms`
    using a tolerance window of `±tolerance_ms` (default ±70 ms).
    Computes:
    - `coherence = confirmed / total_events`
    - `drift_ms_per_min` = slope of linear regression of `(t_ms, residual_offset_ms)` in ms/min
    - `effective_touch_count` = confirmed touches + high-confidence single-modality touches
      when coherence is healthy (recovers touches missed by 1-2 frame visual occlusion).
    """
    cfg = config or load_football_config().fusion
    tolerance_ms = cfg.tolerance_ms

    cal_offset_ms = estimate_calibration_offset_ms(
        video_events=video_events,
        audio_events=audio_events,
        calibration_touch_ms=calibration_touch_ms,
    )

    # Build all candidate pairs within ±tolerance_ms after calibration compensation
    candidate_pairs: list[tuple[int, int, int, int]] = []
    for v_idx, v_ev in enumerate(video_events):
        for a_idx, a_ev in enumerate(audio_events):
            compensated_audio_t = a_ev.t_ms - cal_offset_ms
            residual = compensated_audio_t - v_ev.t_ms
            if abs(residual) <= tolerance_ms:
                candidate_pairs.append((abs(residual), v_idx, a_idx, residual))

    candidate_pairs.sort(key=lambda item: item[0])

    matched_v: set[int] = set()
    matched_a: set[int] = set()
    fused_events: list[FusedTouchEvent] = []
    paired_times_ms: list[float] = []
    paired_residuals_ms: list[float] = []

    for _, v_idx, a_idx, residual in candidate_pairs:
        if v_idx in matched_v or a_idx in matched_a:
            continue
        matched_v.add(v_idx)
        matched_a.add(a_idx)

        v_ev = video_events[v_idx]
        a_ev = audio_events[a_idx]
        fused_t = round(0.5 * (v_ev.t_ms + (a_ev.t_ms - cal_offset_ms)))
        fused_conf = min(1.0, 0.55 * v_ev.confidence + 0.55 * a_ev.confidence)

        fused_events.append(
            FusedTouchEvent(
                t_ms=fused_t,
                estado="confirmed",
                confianza=round(fused_conf, 4),
                video_t_ms=v_ev.t_ms,
                audio_t_ms=a_ev.t_ms,
                offset_ms=residual,
                is_ground_bounce=v_ev.is_ground_bounce,
            )
        )
        paired_times_ms.append(float(fused_t))
        paired_residuals_ms.append(float(residual))

    for v_idx, v_ev in enumerate(video_events):
        if v_idx not in matched_v:
            fused_events.append(
                FusedTouchEvent(
                    t_ms=v_ev.t_ms,
                    estado="video_only",
                    confianza=round(v_ev.confidence * 0.75, 4),
                    video_t_ms=v_ev.t_ms,
                    audio_t_ms=None,
                    offset_ms=None,
                    is_ground_bounce=v_ev.is_ground_bounce,
                )
            )

    for a_idx, a_ev in enumerate(audio_events):
        if a_idx not in matched_a:
            fused_events.append(
                FusedTouchEvent(
                    t_ms=a_ev.t_ms - cal_offset_ms,
                    estado="audio_only",
                    confianza=round(a_ev.confidence * 0.75, 4),
                    video_t_ms=None,
                    audio_t_ms=a_ev.t_ms,
                    offset_ms=None,
                )
            )

    fused_events.sort(key=lambda ev: ev.t_ms)

    confirmed_count = sum(1 for ev in fused_events if ev.estado == "confirmed")
    video_only_count = sum(1 for ev in fused_events if ev.estado == "video_only")
    audio_only_count = sum(1 for ev in fused_events if ev.estado == "audio_only")
    total_events = len(fused_events)

    coherence = (
        confirmed_count / float(total_events) if total_events > 0 else 0.0
    )

    # Drift = linear regression slope of residual offset over time, converted to ms/minute
    drift_ms_per_min = 0.0
    if len(paired_times_ms) >= 2:
        t_arr = np.array(paired_times_ms, dtype=np.float64)
        r_arr = np.array(paired_residuals_ms, dtype=np.float64)
        if float(np.ptp(t_arr)) > 100.0:
            slope_ms_per_ms, _ = np.polyfit(t_arr, r_arr, 1)
            drift_ms_per_min = float(slope_ms_per_ms * 60000.0)

    # Effective touch count: confirmed touches + credible single-modality touches
    # when overall session coherence shows genuine synchronized capture
    if coherence >= 0.50:
        rescued_audio = sum(
            1
            for ev in fused_events
            if ev.estado == "audio_only" and ev.confianza >= 0.45
        )
        rescued_video = sum(
            1
            for ev in fused_events
            if ev.estado == "video_only" and ev.confianza >= 0.45
        )
        effective_touch_count = confirmed_count + rescued_audio + rescued_video
    else:
        effective_touch_count = confirmed_count + video_only_count

    return FusionSummary(
        events=fused_events,
        confirmed_count=confirmed_count,
        video_only_count=video_only_count,
        audio_only_count=audio_only_count,
        effective_touch_count=effective_touch_count,
        coherence=round(coherence, 4),
        drift_ms_per_min=round(drift_ms_per_min, 4),
        estimated_calibration_offset_ms=cal_offset_ms,
    )

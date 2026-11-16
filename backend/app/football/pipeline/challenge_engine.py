from __future__ import annotations

import hashlib
import hmac
import json
import random
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.core.config import settings
from app.football.config import ChallengesConfig, load_football_config
from app.football.pipeline.ball_tracker import BallTrack
from app.football.pipeline.fusion import FusedTouchEvent

CHALLENGE_TYPES: tuple[str, ...] = ("LOW", "HIGH", "SLOW", "FAST")


@dataclass
class SegmentComplianceResult:
    indice: int
    tipo: str
    inicio_servidor_ms: int
    duracion_ms: int
    cumplimiento: float
    latencia_reaccion_ms: int | None
    median_height_diameters: float
    median_interval_s: float
    touch_count: int


@dataclass
class ChallengeEvaluationSummary:
    segments: list[SegmentComplianceResult] = field(default_factory=list)
    mean_compliance: float = 0.0
    mean_reaction_latency_ms: float | None = None
    plan_coherent: bool = True
    incoherent_segments_count: int = 0


def generate_plan(seed: int) -> tuple[list[dict[str, Any]], str]:
    """
    Generate a deterministic 4-6 segment dynamic challenge plan ("the coach says")
    without consecutive duplicate challenge types, signed with HMAC-SHA256.
    """
    cfg = load_football_config()
    rng = random.Random(seed)
    num_segments = rng.randint(
        cfg.challenges.min_segments, cfg.challenges.max_segments
    )

    segments: list[dict[str, Any]] = []
    current_offset_ms = 0
    previous_type: str | None = None

    for idx in range(num_segments):
        candidates = [t for t in CHALLENGE_TYPES if t != previous_type]
        selected_type = rng.choice(candidates)
        duration_ms = rng.randrange(
            cfg.challenges.segment_min_duration_ms,
            cfg.challenges.segment_max_duration_ms + 1,
            500,
        )
        segments.append(
            {
                "indice": idx,
                "tipo": selected_type,
                "inicio_servidor_ms": current_offset_ms,
                "duracion_ms": duration_ms,
            }
        )
        current_offset_ms += duration_ms
        previous_type = selected_type

    payload_obj = {"seed": seed, "segments": segments}
    canonical_json = json.dumps(payload_obj, sort_keys=True, separators=(",", ":"))
    secret_bytes = settings.SECRET_KEY.get_secret_value().encode("utf-8")
    signature = hmac.new(
        secret_bytes, canonical_json.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    signed_plan = json.dumps(
        {"payload": payload_obj, "signature": signature},
        sort_keys=True,
    )
    return segments, signed_plan


def verify_signed_plan(signed_plan_str: str) -> bool:
    """Verify HMAC-SHA256 signature of a stored challenge plan."""
    try:
        parsed = json.loads(signed_plan_str)
        payload_obj = parsed["payload"]
        signature = str(parsed["signature"])
    except (KeyError, ValueError, TypeError):
        return False

    canonical_json = json.dumps(payload_obj, sort_keys=True, separators=(",", ":"))
    secret_bytes = settings.SECRET_KEY.get_secret_value().encode("utf-8")
    expected_sig = hmac.new(
        secret_bytes, canonical_json.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, expected_sig)


def _compute_touch_peak_heights(
    touch_times_ms: list[int],
    track: BallTrack | None,
) -> list[float]:
    """
    For each consecutive pair of touches `(t_k, t_{k+1})`, compute the apex height
    in ball diameters reached during the flight arc between `t_k` and `t_{k+1}`.
    """
    if not touch_times_ms or track is None or not track.points:
        return []

    pts = track.points
    peak_heights: list[float] = []

    for idx, t0 in enumerate(touch_times_ms):
        t1 = (
            touch_times_ms[idx + 1]
            if (idx + 1) < len(touch_times_ms)
            else t0 + 800
        )
        arc_heights = [
            pt.height_diameters for pt in pts if t0 <= pt.t_ms <= t1
        ]
        if arc_heights:
            peak_heights.append(float(max(arc_heights)))
        else:
            nearest_pt = min(pts, key=lambda p: abs(p.t_ms - t0))
            peak_heights.append(float(nearest_pt.height_diameters))

    return peak_heights


def _score_segment_type(
    tipo: str,
    median_height: float,
    median_interval_s: float,
    cfg: ChallengesConfig,
) -> float:
    """
    Score segment compliance in `[0.0, 1.0]` with smooth linear tolerance margin:
    - LOW: median height < 1.5 diameters (tolerance up to 2.1)
    - HIGH: median height > 3.0 diameters (tolerance down to 2.2)
    - SLOW: median interval > 1.0 s (tolerance down to 0.75 s)
    - FAST: median interval < 0.6 s (tolerance up to 0.85 s)
    """
    if tipo == "LOW":
        target = cfg.low_max_height_diameters
        if median_height <= target:
            return 1.0
        tolerance_limit = target + 0.6
        if median_height >= tolerance_limit:
            return 0.0
        return round((tolerance_limit - median_height) / 0.6, 4)

    if tipo == "HIGH":
        target = cfg.high_min_height_diameters
        if median_height >= target:
            return 1.0
        tolerance_floor = max(1.5, target - 0.8)
        if median_height <= tolerance_floor:
            return 0.0
        return round(
            (median_height - tolerance_floor) / (target - tolerance_floor), 4
        )

    if tipo == "SLOW":
        target = cfg.slow_min_interval_s
        if median_interval_s >= target:
            return 1.0
        tolerance_floor = max(0.5, target - 0.25)
        if median_interval_s <= tolerance_floor:
            return 0.0
        return round(
            (median_interval_s - tolerance_floor) / (target - tolerance_floor), 4
        )

    if tipo == "FAST":
        target = cfg.fast_max_interval_s
        if median_interval_s <= target:
            return 1.0
        tolerance_limit = target + 0.25
        if median_interval_s >= tolerance_limit:
            return 0.0
        return round((tolerance_limit - median_interval_s) / 0.25, 4)

    return 0.0


def evaluate_challenge_plan(
    segments_plan: list[dict[str, Any]],
    fused_events: list[FusedTouchEvent],
    track: BallTrack | None = None,
    config: ChallengesConfig | None = None,
) -> ChallengeEvaluationSummary:
    """
    Pure pipeline step (`challenge_engine`):
    Evaluates compliance (`0..1`) and reaction latency (`ms`) for each segment in
    `segments_plan` against `fused_events` and `track`.
    Marks `plan_coherent = False` when a video recorded under a different plan
    exhibits low mean compliance (`< 0.50`) or multiple non-compliant segments.
    """
    cfg = config or load_football_config().challenges
    valid_events = sorted(
        [
            ev
            for ev in fused_events
            if ev.estado in {"confirmed", "video_only", "audio_only"}
        ],
        key=lambda e: e.t_ms,
    )
    all_touch_times = [ev.t_ms for ev in valid_events]
    all_peak_heights = _compute_touch_peak_heights(all_touch_times, track)

    results: list[SegmentComplianceResult] = []
    latencies: list[int] = []

    for seg in sorted(segments_plan, key=lambda s: int(s["indice"])):
        idx = int(seg["indice"])
        tipo = str(seg["tipo"]).upper()
        start_ms = int(seg["inicio_servidor_ms"])
        duration_ms = int(seg["duracion_ms"])
        end_ms = start_ms + duration_ms

        seg_indices = [
            i
            for i, t_ms in enumerate(all_touch_times)
            if start_ms <= t_ms <= end_ms
        ]

        if len(seg_indices) < 2:
            results.append(
                SegmentComplianceResult(
                    indice=idx,
                    tipo=tipo,
                    inicio_servidor_ms=start_ms,
                    duracion_ms=duration_ms,
                    cumplimiento=0.0,
                    latencia_reaccion_ms=None,
                    median_height_diameters=0.0,
                    median_interval_s=0.0,
                    touch_count=len(seg_indices),
                )
            )
            continue

        seg_times = [all_touch_times[i] for i in seg_indices]
        seg_heights = [all_peak_heights[i] for i in seg_indices]
        seg_intervals_s = [
            (seg_times[k + 1] - seg_times[k]) / 1000.0
            for k in range(len(seg_times) - 1)
        ]

        median_height = float(np.median(seg_heights)) if seg_heights else 0.0
        median_interval_s = (
            float(np.median(seg_intervals_s)) if seg_intervals_s else 0.0
        )

        compliance = _score_segment_type(
            tipo=tipo,
            median_height=median_height,
            median_interval_s=median_interval_s,
            cfg=cfg,
        )

        # Reaction latency: time from segment command `start_ms` to the first touch
        # inside the segment that exhibits the target behavior
        reaction_latency_ms: int | None = None
        for local_k, global_i in enumerate(seg_indices):
            t_touch = all_touch_times[global_i]
            h_touch = all_peak_heights[global_i]
            dt_next_s = (
                seg_intervals_s[local_k]
                if local_k < len(seg_intervals_s)
                else median_interval_s
            )
            single_score = _score_segment_type(
                tipo=tipo,
                median_height=h_touch,
                median_interval_s=dt_next_s,
                cfg=cfg,
            )
            if single_score >= 0.65:
                reaction_latency_ms = max(0, t_touch - start_ms)
                latencies.append(reaction_latency_ms)
                break

        results.append(
            SegmentComplianceResult(
                indice=idx,
                tipo=tipo,
                inicio_servidor_ms=start_ms,
                duracion_ms=duration_ms,
                cumplimiento=compliance,
                latencia_reaccion_ms=reaction_latency_ms,
                median_height_diameters=round(median_height, 3),
                median_interval_s=round(median_interval_s, 3),
                touch_count=len(seg_indices),
            )
        )

    mean_compliance = (
        float(np.mean([r.cumplimiento for r in results])) if results else 0.0
    )
    incoherent_count = sum(1 for r in results if r.cumplimiento < 0.35)
    plan_coherent = mean_compliance >= 0.55 and incoherent_count <= (
        len(results) // 3
    )

    mean_latency = (
        round(float(np.mean(latencies)), 2) if latencies else None
    )

    return ChallengeEvaluationSummary(
        segments=results,
        mean_compliance=round(mean_compliance, 4),
        mean_reaction_latency_ms=mean_latency,
        plan_coherent=plan_coherent,
        incoherent_segments_count=incoherent_count,
    )

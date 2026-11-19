from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.celery_app import celery_app
from app.football.config import load_football_config
from app.football.pipeline.audio_events import detect_audio_impact_events
from app.football.pipeline.ball_tracker import BallTrack, track_ball_in_video
from app.football.pipeline.challenge_engine import (
    ChallengeEvaluationSummary,
    evaluate_challenge_plan,
    generate_plan,
)
from app.football.pipeline.features import extract_session_features
from app.football.pipeline.fraud import evaluate_fraud_signals, inspect_video_integrity
from app.football.pipeline.fusion import (
    FusionSummary,
    fuse_audio_video_events,
)
from app.football.pipeline.scoring import score_session_features
from app.football.pipeline.touch_events import detect_video_touch_events

logger = logging.getLogger("skillmatch.football.tasks")

@celery_app.task(name="football.process_session")
def process_session(
    session_id: str,
    video_path: str | None = None,
    audio_path: str | None = None,
    calibration_touch_ms: int | None = None,
    seed: int | None = None,
    segments_plan: list[dict[str, Any]] | None = None,
    client_events: list[dict[str, Any]] | None = None,
    expected_duration_s: float | None = None,
    detected_faces_count: int = 1,
) -> dict[str, Any]:
    """
    Celery pipeline entrypoint task for football skill validation.
    Executes the full pure pipeline in order:
    `ball_tracker -> touch_events -> audio_events -> fusion -> challenge_engine -> features -> scoring -> fraud`.
    """
    cfg = load_football_config()
    logger.info(
        "Processing football validation session_id=%s with config_version=%s",
        session_id,
        cfg.version,
    )

    video_touches: list[dict[str, Any]] = []
    audio_impacts: list[dict[str, Any]] = []
    fusion_payload: dict[str, Any] | None = None
    challenge_payload: dict[str, Any] | None = None
    features_payload: dict[str, Any] | None = None
    scoring_payload: dict[str, Any] | None = None
    fraud_payload: dict[str, Any] | None = None
    tracked_frames = 0

    track: BallTrack | None = None
    candidates = []
    video_integrity: dict[str, Any] | None = None
    actual_video_duration_s: float | None = None

    if video_path and Path(video_path).exists():
        track = track_ball_in_video(video_path)
        tracked_frames = len(track.points)
        if track.fps > 0 and tracked_frames > 0:
            actual_video_duration_s = tracked_frames / float(track.fps)
        candidates = detect_video_touch_events(track)
        video_integrity = inspect_video_integrity(video_path)
        video_touches = [
            {
                "t_ms": c.t_ms,
                "frame_idx": c.frame_idx,
                "height_diameters": round(c.height_diameters, 3),
                "confidence": round(c.confidence, 3),
            }
            for c in candidates
        ]

    audio_events = []
    if audio_path and Path(audio_path).exists():
        audio_events = detect_audio_impact_events(audio_path)
        audio_impacts = [
            {
                "t_ms": a.t_ms,
                "strength": a.strength,
                "confidence": a.confidence,
            }
            for a in audio_events
        ]

    fused_summary = FusionSummary()
    if candidates or audio_events:
        fused_summary = fuse_audio_video_events(
            video_events=candidates,
            audio_events=audio_events,
            calibration_touch_ms=calibration_touch_ms,
        )
        fusion_payload = {
            "confirmed_count": fused_summary.confirmed_count,
            "video_only_count": fused_summary.video_only_count,
            "audio_only_count": fused_summary.audio_only_count,
            "effective_touch_count": fused_summary.effective_touch_count,
            "coherence": fused_summary.coherence,
            "drift_ms_per_min": fused_summary.drift_ms_per_min,
            "estimated_calibration_offset_ms": fused_summary.estimated_calibration_offset_ms,
            "events": [
                {
                    "t_ms": ev.t_ms,
                    "estado": ev.estado,
                    "confianza": ev.confianza,
                }
                for ev in fused_summary.events
            ],
        }

    active_plan = segments_plan
    if active_plan is None and seed is not None:
        active_plan, _ = generate_plan(seed)

    challenge_eval: ChallengeEvaluationSummary | None = None
    if active_plan and fused_summary.events:
        challenge_eval = evaluate_challenge_plan(
            segments_plan=active_plan,
            fused_events=fused_summary.events,
            track=track,
        )
        challenge_payload = {
            "mean_compliance": challenge_eval.mean_compliance,
            "mean_reaction_latency_ms": challenge_eval.mean_reaction_latency_ms,
            "plan_coherent": challenge_eval.plan_coherent,
            "incoherent_segments_count": challenge_eval.incoherent_segments_count,
            "segments": [
                {
                    "indice": s.indice,
                    "tipo": s.tipo,
                    "inicio_servidor_ms": s.inicio_servidor_ms,
                    "duracion_ms": s.duracion_ms,
                    "cumplimiento": s.cumplimiento,
                    "latencia_reaccion_ms": s.latencia_reaccion_ms,
                    "median_height_diameters": s.median_height_diameters,
                    "median_interval_s": s.median_interval_s,
                    "touch_count": s.touch_count,
                }
                for s in challenge_eval.segments
            ],
        }

    if candidates or audio_events:
        features_payload = extract_session_features(
            track=track,
            fusion=fused_summary,
            challenge_eval=challenge_eval,
            session_duration_s=actual_video_duration_s or expected_duration_s,
        )
        scoring_out = score_session_features(features_payload)
        fraud_out = evaluate_fraud_signals(
            fusion=fused_summary,
            challenge_eval=challenge_eval,
            track=track,
            client_events=client_events,
            video_integrity=video_integrity,
            expected_duration_s=expected_duration_s,
            actual_video_duration_s=actual_video_duration_s,
            detected_faces_count=detected_faces_count,
        )

        final_needs_review = (
            scoring_out.requiere_revision or fraud_out.requiere_revision
        )
        scoring_payload = {
            "nivel": scoring_out.nivel,
            "probabilidades": scoring_out.probabilidades,
            "confianza": scoring_out.confianza,
            "requiere_revision": final_needs_review,
            "retroalimentacion": scoring_out.retroalimentacion,
            "version_modelo": scoring_out.version_modelo,
            "version_config": scoring_out.version_config,
        }
        fraud_payload = {
            "puntaje_riesgo": fraud_out.puntaje_riesgo,
            "requiere_revision": fraud_out.requiere_revision,
            "invalidada": fraud_out.invalidada,
            "incidencias": [
                {
                    "tipo": inc.tipo,
                    "severidad": inc.severidad,
                    "t_ms": inc.t_ms,
                    "detalle": inc.detalle,
                }
                for inc in fraud_out.incidencias
            ],
        }

    status_label = "processed_phase0_stub"
    if challenge_payload is not None:
        status_label = "processed_phase4"
    elif video_path and audio_path:
        status_label = "processed_phase3"
    elif video_path:
        status_label = "processed_phase2"

    return {
        "session_id": str(session_id),
        "status": status_label,
        "config_version": cfg.version,
        "config_hash": cfg.config_hash,
        "tracked_frames": tracked_frames,
        "video_touch_count": len(video_touches),
        "video_touches": video_touches,
        "audio_impact_count": len(audio_impacts),
        "fusion": fusion_payload,
        "challenges": challenge_payload,
        "features": features_payload,
        "scoring": scoring_payload,
        "fraud": fraud_payload,
        "processed_at": datetime.now(UTC).isoformat(),
    }

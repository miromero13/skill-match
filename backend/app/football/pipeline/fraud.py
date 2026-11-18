from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.football.config import FraudConfig, load_football_config
from app.football.pipeline.ball_tracker import BallTrack
from app.football.pipeline.challenge_engine import ChallengeEvaluationSummary
from app.football.pipeline.fusion import FusionSummary


@dataclass
class DetectedFraudSignal:
    tipo: str
    severidad: str  # "low" | "medium" | "high"
    t_ms: int
    detalle: str
    weight: float


@dataclass
class FraudEvaluationOutput:
    puntaje_riesgo: float
    requiere_revision: bool
    invalidada: bool
    incidencias: list[DetectedFraudSignal] = field(default_factory=list)


def inspect_video_integrity(
    video_path: str | Path,
) -> dict[str, Any]:
    """
    Inspect frame-to-frame pixel differences and border translation to detect:
    1. Repeated frames (`frame_repeat_count`) or abrupt scene cuts (`frame_cut_count`)
    2. Camera instability (`camera_jitter_px`)
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return {
            "frame_repeat_count": 0,
            "frame_cut_count": 0,
            "camera_jitter_px": 0.0,
            "first_anomaly_ms": 0,
        }

    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    if fps <= 0:
        fps = 30.0

    prev_gray: np.ndarray | None = None
    frame_diffs: list[float] = []
    border_shifts: list[float] = []
    repeat_count = 0
    cut_count = 0
    first_anomaly_ms = 0
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if prev_gray is not None:
            diff_mat = cv2.absdiff(gray, prev_gray)
            mean_diff = float(np.mean(diff_mat))
            frame_diffs.append(mean_diff)

            # Top border strip (static background area) difference for camera stability
            top_strip_diff = float(np.mean(diff_mat[:24, :]))
            border_shifts.append(top_strip_diff)

            if mean_diff < 0.02 and frame_idx > 2:
                repeat_count += 1
                if first_anomaly_ms == 0:
                    first_anomaly_ms = round((frame_idx * 1000.0) / fps)
            elif mean_diff > 42.0:
                cut_count += 1
                if first_anomaly_ms == 0:
                    first_anomaly_ms = round((frame_idx * 1000.0) / fps)

        prev_gray = gray
        frame_idx += 1

    cap.release()

    camera_jitter = float(np.mean(border_shifts)) if border_shifts else 0.0
    return {
        "frame_repeat_count": repeat_count,
        "frame_cut_count": cut_count,
        "camera_jitter_px": round(camera_jitter, 3),
        "first_anomaly_ms": first_anomaly_ms,
    }


def evaluate_fraud_signals(
    fusion: FusionSummary,
    challenge_eval: ChallengeEvaluationSummary | None = None,
    track: BallTrack | None = None,
    client_events: list[dict[str, Any]] | None = None,
    video_integrity: dict[str, Any] | None = None,
    expected_duration_s: float | None = None,
    actual_video_duration_s: float | None = None,
    detected_faces_count: int = 1,
    person_in_frame_ratio: float = 1.0,
    config: FraudConfig | None = None,
) -> FraudEvaluationOutput:
    """
    Pure pipeline step (`fraud`):
    Evaluates all 10 anti-fraud signals from Section 8 and computes a weighted
    risk score in `[0.0, 100.0]` plus structured `DetectedFraudSignal` incidents.
    High risk marks `requiere_revision = True` or `invalidada = True` (never discards silently).
    """
    full_cfg = load_football_config()
    cfg = config or full_cfg.fraud
    fusion_cfg = full_cfg.fusion
    chal_cfg = full_cfg.challenges
    weights = cfg.weights

    incidents: list[DetectedFraudSignal] = []

    # 1. Low audio-video coherence (`low_av_coherence`)
    if len(fusion.events) >= 3 and fusion.coherence < fusion_cfg.min_coherence:
        w = float(weights.get("low_av_coherence", 25.0))
        incidents.append(
            DetectedFraudSignal(
                tipo="low_av_coherence",
                severidad="high" if fusion.coherence < 0.40 else "medium",
                t_ms=0,
                detalle=f"Coherencia audio-video baja ({fusion.coherence:.2f} < {fusion_cfg.min_coherence:.2f}).",
                weight=w,
            )
        )

    # 2. High audio-video clock drift (`high_av_drift`)
    if abs(fusion.drift_ms_per_min) > fusion_cfg.max_drift_ms_per_min:
        w = float(weights.get("high_av_drift", 15.0))
        incidents.append(
            DetectedFraudSignal(
                tipo="high_av_drift",
                severidad="medium",
                t_ms=0,
                detalle=f"Deriva temporal audio-video elevada ({fusion.drift_ms_per_min:.1f} ms/min).",
                weight=w,
            )
        )

    # 3. Client tab/focus/fullscreen loss events (`tab_or_focus_loss`)
    if client_events:
        w = float(weights.get("tab_or_focus_loss", 20.0))
        for idx, ev in enumerate(client_events):
            ev_type = str(ev.get("tipo") or ev.get("event") or "tab_hidden")
            t_ms = int(ev.get("t_ms") or ev.get("timestamp_ms") or 0)
            incidents.append(
                DetectedFraudSignal(
                    tipo=ev_type,
                    severidad="medium",
                    t_ms=t_ms,
                    detalle=f"Evento de supervisión en cliente detectado: {ev_type}.",
                    weight=w if idx == 0 else w * 0.5,
                )
            )

    # 4. Repeated frames or abrupt scene cuts (`frame_cut_or_repeat`)
    if video_integrity:
        repeats = int(video_integrity.get("frame_repeat_count", 0))
        cuts = int(video_integrity.get("frame_cut_count", 0))
        if repeats >= 4 or cuts >= 1:
            w = float(weights.get("frame_cut_or_repeat", 25.0))
            incidents.append(
                DetectedFraudSignal(
                    tipo="frame_cut_or_repeat",
                    severidad="high" if cuts >= 1 else "medium",
                    t_ms=int(video_integrity.get("first_anomaly_ms", 0)),
                    detalle=f"Anomalía de continuidad de video (cortes={cuts}, fotogramas repetidos={repeats}).",
                    weight=w,
                )
            )

        # 5. Unstable / non-fixed camera (`camera_unstable`)
        jitter = float(video_integrity.get("camera_jitter_px", 0.0))
        if jitter > 8.5:
            w = float(weights.get("camera_unstable", 15.0))
            incidents.append(
                DetectedFraudSignal(
                    tipo="camera_unstable",
                    severidad="medium",
                    t_ms=0,
                    detalle=f"Movimiento excesivo de cámara detectado (jitter={jitter:.2f}).",
                    weight=w,
                )
            )

    # 6. Ball or person out of frame (`out_of_frame`)
    ball_out_ratio = 0.0
    if track and track.points:
        margin_pts = [
            pt
            for pt in track.points
            if pt.x < 8.0
            or pt.x > (track.frame_width - 8.0)
            or pt.y < 8.0
            or pt.y > (track.frame_height - 8.0)
        ]
        ball_out_ratio = len(margin_pts) / float(len(track.points))
    if person_in_frame_ratio < 0.80 or ball_out_ratio > 0.25:
        w = float(weights.get("out_of_frame", 15.0))
        incidents.append(
            DetectedFraudSignal(
                tipo="out_of_frame",
                severidad="medium",
                t_ms=0,
                detalle="Participante o balón fuera del encuadre durante parte de la sesión.",
                weight=w,
            )
        )

    # 7. More than one face in frame (`multiple_faces`)
    if detected_faces_count > 1:
        w = float(weights.get("multiple_faces", 30.0))
        incidents.append(
            DetectedFraudSignal(
                tipo="multiple_faces",
                severidad="high",
                t_ms=0,
                detalle=f"Se detectaron {detected_faces_count} rostros simultáneos en escena.",
                weight=w,
            )
        )

    # 7.1. Ball absence in video (`no_ball_detected`)
    if (track is None or len(track.points) == 0) and len(fusion.events) == 0:
        w = float(weights.get("no_ball_detected", 50.0))
        incidents.append(
            DetectedFraudSignal(
                tipo="no_ball_detected",
                severidad="high",
                t_ms=0,
                detalle="No se detectó ningún balón de fútbol en movimiento en la grabación.",
                weight=w,
            )
        )

    # 8 & 9. Unrealistic reaction latency (< 150 ms or absent) and plan sequence mismatch
    if challenge_eval is not None and challenge_eval.segments:
        min_latency_ms = round(chal_cfg.min_reaction_latency_s * 1000.0)
        too_fast_segments = [
            s
            for s in challenge_eval.segments
            if s.latencia_reaccion_ms is not None
            and s.latencia_reaccion_ms < min_latency_ms
        ]
        missing_latency_segments = [
            s for s in challenge_eval.segments if s.latencia_reaccion_ms is None
        ]
        if too_fast_segments or len(missing_latency_segments) == len(
            challenge_eval.segments
        ):
            w = float(weights.get("unrealistic_reaction_latency", 20.0))
            incidents.append(
                DetectedFraudSignal(
                    tipo="unrealistic_reaction_latency",
                    severidad="high" if too_fast_segments else "medium",
                    t_ms=too_fast_segments[0].inicio_servidor_ms
                    if too_fast_segments
                    else 0,
                    detalle=f"Latencia de reacción irreal (< {min_latency_ms} ms) o ausente ante las órdenes.",
                    weight=w,
                )
            )

        if not challenge_eval.plan_coherent:
            w = float(weights.get("plan_sequence_mismatch", 35.0))
            incidents.append(
                DetectedFraudSignal(
                    tipo="plan_sequence_mismatch",
                    severidad="high",
                    t_ms=0,
                    detalle=(
                        f"La secuencia de ejecución no coincide con el plan emitido "
                        f"(cumplimiento medio {challenge_eval.mean_compliance:.2f})."
                    ),
                    weight=w,
                )
            )

    # 10. Metadata / duration inconsistency (`duration_mismatch`)
    if (
        expected_duration_s is not None
        and actual_video_duration_s is not None
        and abs(actual_video_duration_s - expected_duration_s) > 4.5
    ):
        w = float(weights.get("duration_mismatch", 20.0))
        incidents.append(
            DetectedFraudSignal(
                tipo="duration_mismatch",
                severidad="medium",
                t_ms=0,
                detalle=(
                    f"Duración del video ({actual_video_duration_s:.1f}s) inconsistente "
                    f"con la duración de la sesión ({expected_duration_s:.1f}s)."
                ),
                weight=w,
            )
        )

    raw_risk = sum(inc.weight for inc in incidents)
    risk_score = round(min(100.0, max(0.0, raw_risk)), 2)
    invalidada = risk_score >= cfg.invalid_risk_threshold
    requiere_revision = risk_score >= cfg.review_risk_threshold or invalidada

    return FraudEvaluationOutput(
        puntaje_riesgo=risk_score,
        requiere_revision=requiere_revision,
        invalidada=invalidada,
        incidencias=incidents,
    )

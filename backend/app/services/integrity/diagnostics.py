"""Opt-in tuning diagnostics (T11): one numeric JSON line per audiovisual window.

The thresholds in ``thresholds.py`` were tuned on synthetic data; this log records what the engine measured on real,
labelled sessions so they can be tuned (``scripts/integrity_tuning_report.py``). Only scalar measurements are written:
never an image, audio samples, an embedding, the voiceprint, the gaze zone or the occlusion reference.
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Sequence

from app.services.continuous_supervision_service import ContinuousSupervisionService
from app.services.integrity import frame_analyzer as frames
from app.services.integrity.engine import IntegrityEngine
from app.services.integrity.models import FrameObservation, GazeSample, GazeZone, WindowObservation
from app.services.integrity.policy import SupervisionProfile

logger = logging.getLogger(__name__)

VOICED_CHUNK_S = 0.03  # AudioObservation.voiced_chunks counts 30 ms VAD chunks


def assess_observed(
    frames_b64: list[str], audio_samples: Optional[list[float]], mode: str = "UNIFIED",
    biometric_embedding_json: Optional[str] = None, trial_id: Optional[str] = None,
    duration_ms: Optional[int] = None, gaze_zone: Optional[Mapping[str, float]] = None,
    frame_times_ms: Optional[Sequence[int]] = None, gaze_samples: Sequence[Any] = (),
    observed_at_ms: Optional[int] = None, voiceprint: Optional[Mapping[str, Any]] = None,
) -> tuple[dict[str, Any], WindowObservation]:
    """``ContinuousSupervisionService.assess_window`` (same wiring and verdict) that also returns the observation."""
    service = ContinuousSupervisionService
    engine = IntegrityEngine(service._frame_analyzer(True), service._audio_analyzer())
    observation = engine.observe_window(
        frames_b64, audio_samples, duration_ms, frames.parse_reference_embedding(biometric_embedding_json),
        trial_id, gaze_zone=GazeZone.from_dict(gaze_zone) if gaze_zone else None, frame_times_ms=frame_times_ms,
        gaze_samples=[
            GazeSample(t_ms=s.t_ms, face_count=s.face_count, head_pitch=s.head_pitch, head_yaw=s.head_yaw,
                       gaze_h=s.gaze_h, gaze_v=s.gaze_v, blink=s.blink, mouth_open=getattr(s, "mouth_open", None))
            for s in gaze_samples
        ],
        window_start_ms=observed_at_ms, voiceprint=voiceprint,
    )
    verdict = SupervisionProfile(gaze_runs=service._store()).evaluate(observation)
    return verdict.to_dict(), observation


def _numbers(pairs: Mapping[str, Any]) -> dict[str, Any]:
    """Scalars only (rounded floats), without the measurements that were not made."""
    out: dict[str, Any] = {}
    for key, value in pairs.items():
        if value is None or isinstance(value, (list, tuple, dict)):
            continue
        out[key] = round(float(value), 4) if isinstance(value, float) else value
    return out


def _frame(frame: FrameObservation, at_ms: Optional[int]) -> dict[str, Any]:
    occlusion = frame.occlusion
    return _numbers({
        "t_ms": at_ms, "face_count": frame.face_count, "pitch_deg": frame.pitch_deg, "yaw_deg": frame.yaw_deg,
        "gaze_h": frame.gaze_h, "gaze_v": frame.gaze_v, "blink": frame.blink,
        "mouth_open": frame.mouth_open_score, "identity_similarity": frame.identity_similarity,
        "face_score": frame.face_score, "frame_delta": frame.frame_delta, "camera_blocked": frame.camera_blocked,
        "occlusion_face": occlusion.face if occlusion else None,
        "occlusion_mouth": occlusion.mouth if occlusion else None,
        "occlusion_measured": occlusion.measured if occlusion else None,
        "occlusion_signals": ",".join(occlusion.signals) if occlusion and occlusion.signals else None,
    })


def window_record(
    observation: WindowObservation, anomalies: Sequence[str], window_id: Any, label: Optional[str], ts: float,
) -> dict[str, Any]:
    audio, sync = observation.audio, observation.lip_sync
    times = observation.frame_times_ms
    return {
        "ts": datetime.fromtimestamp(ts, timezone.utc).isoformat(),
        "window_id": str(window_id),
        "label": label,
        "anomalies": list(anomalies),
        "window": _numbers({
            "duration_ms": observation.duration_ms, "frames": len(observation.frames),
            "video_missing": observation.video_missing, "audio_missing": observation.audio_missing,
            "mouth_moving": observation.mouth_moving,
            "client_mismatch": observation.gaze.client_mismatch if observation.gaze else None,
        }),
        "frames": [_frame(f, times[i] if i < len(times) else None) for i, f in enumerate(observation.frames)],
        "audio": _numbers({
            "rms": audio.rms, "speech_detected": audio.speech_detected, "voiced_s": audio.voiced_chunks * VOICED_CHUNK_S,
            "speakers": audio.speakers, "overlap_s": audio.overlap_s, "voice_similarity": audio.voice_similarity,
            "voice_status": audio.voice_status, "multiple_speakers": audio.multiple_speakers,
            "foreign_voice": audio.foreign_voice, "high_noise": audio.high_noise, "diarized": audio.diarized,
        }),
        "lip_sync": _numbers({
            "verdict": sync.verdict, "correlation": sync.correlation, "overlap": sync.overlap, "lag_ms": sync.lag_ms,
            "source": sync.source,
        }),
    }


def _append(directory: str, trial_id: str, record: dict[str, Any]) -> None:
    os.makedirs(directory, mode=0o700, exist_ok=True)
    with open(os.path.join(directory, f"{trial_id}.jsonl"), "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, separators=(",", ":")) + "\n")


async def write_window(directory: str, trial_id: Any, record: dict[str, Any]) -> None:
    """Appends the line off the event loop; a failure is a warning, never a failed request."""
    try:
        await asyncio.to_thread(_append, directory, str(trial_id), record)
    except Exception as error:  # noqa: BLE001 - diagnostics must never break supervision
        logger.warning("Integrity diagnostics could not be written (%s)", type(error).__name__)

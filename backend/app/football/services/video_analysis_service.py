"""Admin test tool: analyze an uploaded juggling video (odd/tasks/football-video-analysis.md).

Never raises for a received request: every failure (no file, oversize, unreadable video,
detector crash, classifier loading error) becomes a complete 0-touch result with an honest
note. Nothing is persisted, no attempts are consumed and nothing leaves the server; the
temporary copy of the upload is always deleted.
"""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Any

import cv2
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.football.pipeline import efficientdet_ball_detector
from app.football.pipeline.ball_tracker import track_ball_in_video
from app.football.pipeline.features import compute_touch_streaks, extract_session_features
from app.football.pipeline.fusion import fuse_audio_video_events
from app.football.pipeline.scoring import (
    LevelClassifierProtocol,
    ScoringOutput,
    generate_template_feedback,
    score_session_features,
)
from app.football.pipeline.touch_events import detect_video_touch_events
from app.football.services import session_service

logger = logging.getLogger("skillmatch.football.video_analysis")

# Matches nginx `client_max_body_size 200m` (frontend/nginx/default.conf).
MAX_UPLOAD_BYTES = 200 * 1024 * 1024
MAX_ANALYZED_SECONDS = 180.0
_COPY_CHUNK_BYTES = 1024 * 1024
_ALLOWED_SUFFIXES = {".mp4", ".webm", ".mov", ".m4v", ".mkv", ".avi"}

DETECTOR_FUSED = "mediapipe-efficientdet-lite0+classical"
DETECTOR_CLASSICAL = "classical"
NO_TOUCH_LEVEL = "Principiante"

NOTE_NO_FILE = "No se recibió ningún archivo de video."
NOTE_EMPTY_FILE = "El archivo recibido está vacío."
NOTE_OVERSIZE = "El video supera el tamaño máximo de 200 MB; no se analizó."
NOTE_UNREADABLE = "No se pudo leer el video (formato no soportado o archivo dañado)."
NOTE_NO_BALL = "No se detectó balón en el video."
NOTE_NO_TOUCHES = "No se detectaron toques válidos."
NOTE_TRUNCATED = f"Se analizaron solo los primeros {int(MAX_ANALYZED_SECONDS)} s del video."
NOTE_MODEL_MISSING = "Modelo EfficientDet-Lite0 no instalado; se usó solo el detector clásico."
NOTE_MODEL_LOAD_FAILED = (
    "No se pudo cargar el modelo EfficientDet-Lite0; se usó solo el detector clásico."
)
NOTE_MODEL_RUNTIME_FAILED = (
    "El detector EfficientDet-Lite0 falló durante el análisis; se repitió con el detector clásico."
)
NOTE_ANALYSIS_FAILED = "Ocurrió un fallo interno al analizar el video; se informa sin toques."
NOTE_CLASSIFIER_FALLBACK = (
    "No se pudo cargar el clasificador entrenado; se usó el clasificador por reglas."
)

# An upload has no dynamic challenge plan and no synchronized audio. The level
# classifier gets the same neutral values the trainer imputes for bare clips
# (`ml/train/train_models.py::_FEATURE_DEFAULTS`) so the upload is not penalized.
_NEUTRAL_CLASSIFIER_FEATURES: dict[str, float] = {
    "mean_challenge_compliance": 1.0,
    "av_coherence": 1.0,
}
# Feedback templates comment on challenge compliance outside (0.60, 0.80); a value
# inside that band keeps them from praising/criticizing challenges that never existed.
_FEEDBACK_NO_CHALLENGE_COMPLIANCE = 0.7


def _empty_payload(detector: str = DETECTOR_CLASSICAL) -> dict[str, Any]:
    return {
        "analysis_complete": False,
        "ball_detected": False,
        "detector": detector,
        "frames_analyzed": 0,
        "ball_frames": 0,
        "duration_seconds": 0.0,
        "total_touches": 0,
        "max_streak": 0,
        "streaks": [],
        "ground_contacts": 0,
        "notes": [],
    }


def _apply_scoring(payload: dict[str, Any], scoring: ScoringOutput) -> dict[str, Any]:
    """Merge a `ScoringOutput`; the official zero-touch "No calificado" maps to Principiante."""
    zero_touches = payload["total_touches"] == 0
    payload.update(
        score_1_100=1.0 if zero_touches else float(scoring.puntaje_1_100),
        level=NO_TOUCH_LEVEL if zero_touches else scoring.nivel,
        level_probabilities=dict(scoring.probabilidades),
        confidence=float(scoring.confianza),
        model_version=scoring.version_modelo,
        feedback={
            "fortalezas": list(scoring.retroalimentacion.get("fortalezas", [])),
            "mejoras": list(scoring.retroalimentacion.get("mejoras", [])),
        },
    )
    return payload


def zero_touch_result(
    notes: list[str],
    classifier: LevelClassifierProtocol | None = None,
    detector: str = DETECTOR_CLASSICAL,
) -> dict[str, Any]:
    """Complete, honest result for a file that could not be analyzed."""
    payload = _empty_payload(detector)
    payload["notes"] = list(notes)
    return _apply_scoring(
        payload, score_session_features({"total_touches": 0}, classifier=classifier)
    )


def _probe_video(video_path: Path) -> tuple[float, int, int] | None:
    """`(fps, frame_count, width)` or `None` when OpenCV cannot decode a single frame."""
    cap = cv2.VideoCapture(str(video_path))
    try:
        if not cap.isOpened():
            return None
        ok, frame = cap.read()
        if not ok or frame is None:
            return None
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        if fps <= 0 or fps > 1000:
            fps = 30.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or frame.shape[1])
        return fps, frame_count, width
    finally:
        cap.release()


def _build_fused_detector(
    model_path: Path, frame_width: int, fps: float, notes: list[str]
) -> efficientdet_ball_detector.FusedEfficientDetClassicalDetector | None:
    if not model_path.is_file():
        notes.append(NOTE_MODEL_MISSING)
        return None
    try:
        model = efficientdet_ball_detector.MediaPipeEfficientDetBallDetector(model_path)
    except Exception as exc:  # corrupt weights, mediapipe/EGL unavailable, ...
        logger.warning("EfficientDet-Lite0 could not be loaded: %s", exc)
        notes.append(NOTE_MODEL_LOAD_FAILED)
        return None
    return efficientdet_ball_detector.FusedEfficientDetClassicalDetector(
        model_detector=model, frame_width=frame_width, fps=fps
    )


def analyze_video_file(
    video_path: str | Path,
    classifier: LevelClassifierProtocol | None = None,
    model_path: Path | None = None,
    max_seconds: float = MAX_ANALYZED_SECONDS,
    extra_notes: list[str] | None = None,
) -> dict[str, Any]:
    """CPU-bound, synchronous: tracking -> touches -> streaks -> level. Never raises."""
    notes: list[str] = list(extra_notes or [])
    try:
        return _analyze(Path(video_path), classifier, model_path, max_seconds, notes)
    except Exception:
        logger.exception("Unexpected failure analyzing uploaded football video")
        return zero_touch_result(notes + [NOTE_ANALYSIS_FAILED], classifier)


def _analyze(
    video_path: Path,
    classifier: LevelClassifierProtocol | None,
    model_path: Path | None,
    max_seconds: float,
    notes: list[str],
) -> dict[str, Any]:
    probe = _probe_video(video_path)
    if probe is None:
        return zero_touch_result(notes + [NOTE_UNREADABLE], classifier)
    fps, frame_count, width = probe
    max_frames = max(1, round(max_seconds * fps))

    resolved_model = model_path or efficientdet_ball_detector.efficientdet_model_path()
    fused = _build_fused_detector(resolved_model, width, fps, notes)
    detector_name = DETECTOR_FUSED if fused is not None else DETECTOR_CLASSICAL
    try:
        try:
            track = track_ball_in_video(video_path, detector=fused, max_frames=max_frames)
        except ValueError:
            return zero_touch_result(notes + [NOTE_UNREADABLE], classifier, detector_name)
        except Exception:
            if fused is None:
                raise
            logger.exception("Fused EfficientDet detector failed; retrying classical only")
            notes.append(NOTE_MODEL_RUNTIME_FAILED)
            detector_name = DETECTOR_CLASSICAL
            track = track_ball_in_video(video_path, detector=None, max_frames=max_frames)
    finally:
        if fused is not None:
            fused.close()

    frames_read = track.frames_read
    if frames_read == 0:
        return zero_touch_result(notes + [NOTE_UNREADABLE], classifier, detector_name)
    if frame_count > frames_read and frames_read >= max_frames:
        notes.append(NOTE_TRUNCATED)

    duration_s = frames_read / float(track.fps or fps)
    candidates = detect_video_touch_events(track)
    fusion = fuse_audio_video_events(video_events=candidates, audio_events=[])
    features = extract_session_features(
        track=track, fusion=fusion, challenge_eval=None, session_duration_s=duration_s
    )
    streaks = compute_touch_streaks(fusion)
    ball_frames = sum(1 for pt in track.points if not pt.interpolated)
    ball_detected = bool(track.points) and ball_frames > 0

    payload = _empty_payload(detector_name)
    payload.update(
        analysis_complete=True,
        ball_detected=ball_detected,
        frames_analyzed=frames_read,
        ball_frames=ball_frames,
        duration_seconds=round(duration_s, 2),
        total_touches=int(features["total_touches"]),
        max_streak=int(features["max_streak"]),
        streaks=streaks,
        ground_contacts=int(features["ground_bounce_count"]),
    )
    if not ball_detected:
        notes.append(NOTE_NO_BALL)
    elif payload["total_touches"] == 0:
        notes.append(NOTE_NO_TOUCHES)
    payload["notes"] = notes

    scoring = score_session_features(
        {**features, **_NEUTRAL_CLASSIFIER_FEATURES}, classifier=classifier
    )
    _apply_scoring(payload, scoring)
    if payload["total_touches"] > 0:
        payload["feedback"] = generate_template_feedback(
            features={
                **features,
                "mean_challenge_compliance": _FEEDBACK_NO_CHALLENGE_COMPLIANCE,
            },
            nivel=payload["level"],
        )
    return payload


def _upload_suffix(filename: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    return suffix if suffix in _ALLOWED_SUFFIXES else ".mp4"


async def _spool_upload(upload: UploadFile, target: Path) -> int | None:
    """Copy the upload to `target`; return its size, or `None` when it exceeds the cap."""
    size = 0
    with target.open("wb") as output:
        while chunk := await upload.read(_COPY_CHUNK_BYTES):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                return None
            await run_in_threadpool(output.write, chunk)
    return size


async def _resolve_classifier(
    db: AsyncSession, notes: list[str]
) -> LevelClassifierProtocol | None:
    try:
        return await session_service._load_active_level_classifier(db)
    except Exception as exc:  # DB or artifact storage unavailable
        logger.warning("Active level classifier unavailable for video analysis: %s", exc)
        notes.append(NOTE_CLASSIFIER_FALLBACK)
        return None


def _last_resort_payload() -> dict[str, Any]:
    """Static result used only if even the scoring of a 0-touch result fails."""
    payload = _empty_payload()
    payload.update(
        notes=[NOTE_ANALYSIS_FAILED],
        score_1_100=1.0,
        level=NO_TOUCH_LEVEL,
        level_probabilities={
            "Principiante": 1.0,
            "Intermedio": 0.0,
            "Avanzado": 0.0,
            "Experto": 0.0,
        },
        confidence=0.0,
        model_version="unavailable",
        feedback={"fortalezas": [], "mejoras": []},
    )
    return payload


async def analyze_uploaded_video(
    db: AsyncSession, upload: UploadFile | None
) -> dict[str, Any]:
    """Async entry point for the admin endpoint; always returns a complete result."""
    try:
        return await _analyze_uploaded_video(db, upload)
    except Exception:
        logger.exception("Video analysis could not even build a 0-touch result")
        return _last_resort_payload()


async def _analyze_uploaded_video(
    db: AsyncSession, upload: UploadFile | None
) -> dict[str, Any]:
    notes: list[str] = []
    classifier = await _resolve_classifier(db, notes)
    if upload is None:
        return zero_touch_result(notes + [NOTE_NO_FILE], classifier)

    fd, temp_name = tempfile.mkstemp(
        prefix="skillmatch-football-upload-", suffix=_upload_suffix(upload.filename)
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        size = await _spool_upload(upload, temp_path)
        if size is None:
            return zero_touch_result(notes + [NOTE_OVERSIZE], classifier)
        if size == 0:
            return zero_touch_result(notes + [NOTE_EMPTY_FILE], classifier)
        return await run_in_threadpool(
            analyze_video_file, temp_path, classifier, None, MAX_ANALYZED_SECONDS, notes
        )
    except Exception:
        logger.exception("Unexpected failure receiving uploaded football video")
        return zero_touch_result(notes + [NOTE_ANALYSIS_FAILED], classifier)
    finally:
        temp_path.unlink(missing_ok=True)

"""`analyze_video`: one local pass over a video -> compact, JSON-serializable measurements.

Never raises. Nothing leaves the server (AGENTS.md §1.1): pose via the local MediaPipe model, ball via the
existing football pipeline. A missing model is reported in Spanish notes, never replaced by fake data.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.skill_validation import pose as pose_module
from app.skill_validation.contract import ENGINE_VERSION

logger = logging.getLogger("skillmatch.skill_validation.analysis")

POSE_OK = "ok"
POSE_NOT_REQUESTED = "not_requested"
POSE_MODEL_UNAVAILABLE = "model_unavailable"
POSE_FAILED = "failed"
POSE_UNREADABLE = "unreadable"
BALL_OK = "ok"
BALL_NOT_REQUESTED = "not_requested"
BALL_FAILED = "failed"

NOTE_UNREADABLE = "No se pudo leer el video (formato no soportado o archivo dañado)."
NOTE_POSE_MODEL_MISSING = "El modelo de pose no está instalado; no se pudo analizar el movimiento."
NOTE_POSE_MODEL_LOAD_FAILED = "No se pudo cargar el modelo de pose; no se pudo analizar el movimiento."
NOTE_POSE_FAILED = "Ocurrió un fallo interno al analizar la pose; no se pudo analizar el movimiento."
NOTE_NO_PERSON = "No se detectó a ninguna persona en el video."
NOTE_LOW_PERSON = "La persona se detectó solo en el {pct}% del video; graba el cuerpo completo y bien iluminado."
NOTE_TRUNCATED = "Se analizaron solo los primeros {secs} s del video."
NOTE_BALL_FAILED = "Ocurrió un fallo interno al analizar el balón; se informa sin toques."
NOTE_NO_BALL = "No se detectó balón en el video."
NOTE_NO_TOUCHES = "No se detectaron toques válidos."
NOTE_BALL_MODEL_MISSING = "Modelo EfficientDet-Lite0 no instalado; se usó solo el detector clásico de balón."
NOTE_BALL_MODEL_LOAD_FAILED = "No se pudo cargar el modelo EfficientDet-Lite0; se usó solo el detector clásico."

LOW_PERSON_RATIO = 0.5


def _empty(notes: list[str]) -> dict[str, Any]:
    return {
        "engine_version": ENGINE_VERSION,
        "readable": False,
        "duration_seconds": 0.0,
        "frames_analyzed": 0,
        "pose": None,
        "pose_status": POSE_UNREADABLE,
        "ball": None,
        "ball_status": BALL_NOT_REQUESTED,
        "notes": notes,
    }


def _probe(path: Path) -> tuple[float, int, int, int] | None:
    """(fps, frame_count, width, height) or None when no frame decodes."""
    if not path.is_file():
        return None
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            return None
        ok, frame = cap.read()
        if not ok or frame is None:
            return None
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        if not (0 < fps <= 1000):
            fps = 30.0
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        return fps, max(0, count), frame.shape[1], frame.shape[0]
    finally:
        cap.release()


def _downscale(frame: np.ndarray) -> np.ndarray:
    h, w = frame.shape[:2]
    side = max(h, w)
    if side <= pose_module.MAX_FRAME_SIDE:
        return frame
    scale = pose_module.MAX_FRAME_SIDE / side
    return cv2.resize(frame, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)


def _extract_pose(path: Path, fps: float, max_seconds: float, extractor) -> tuple[dict[str, Any], int, bool]:
    """Sample ~SAMPLE_FPS frames by timestamp; returns (pose block, frames read, truncated)."""
    cap = cv2.VideoCapture(str(path))
    rows: list[tuple[list[float], list[float]] | None] = []
    step = 1.0 / pose_module.SAMPLE_FPS
    next_t = 0.0
    index = 0
    truncated = False
    last_ts = -1
    try:
        while True:
            t = index / fps
            if t > max_seconds:
                truncated = cap.grab()
                break
            if not cap.grab():
                break
            index += 1
            if t + 1e-9 < next_t:
                continue
            next_t += step
            while next_t <= t:
                next_t += step
            ok, frame = cap.retrieve()
            if not ok or frame is None:
                continue
            rgb = cv2.cvtColor(_downscale(frame), cv2.COLOR_BGR2RGB)
            ts = max(last_ts + 1, int(round(t * 1000)))
            last_ts = ts
            rows.append(extractor.process(rgb, ts))
    finally:
        cap.release()
    sampled_fps = len(rows) / (index / fps) if index and fps else pose_module.SAMPLE_FPS
    block = pose_module.build_signature(rows, min(pose_module.SAMPLE_FPS, sampled_fps) if rows else pose_module.SAMPLE_FPS)
    return block, index, truncated


def _analyze_ball(path: Path, fps: float, width: int, max_seconds: float, notes: list[str]) -> dict[str, Any]:
    from app.football.pipeline import efficientdet_ball_detector
    from app.football.pipeline.ball_tracker import track_ball_in_video
    from app.football.pipeline.features import compute_touch_streaks, extract_session_features
    from app.football.pipeline.fusion import fuse_audio_video_events
    from app.football.pipeline.touch_events import detect_video_touch_events

    fused = None
    model_path = efficientdet_ball_detector.efficientdet_model_path()
    if not model_path.is_file():
        notes.append(NOTE_BALL_MODEL_MISSING)
    else:
        try:
            model = efficientdet_ball_detector.MediaPipeEfficientDetBallDetector(model_path)
            fused = efficientdet_ball_detector.FusedEfficientDetClassicalDetector(
                model_detector=model, frame_width=width, fps=fps
            )
        except Exception as exc:
            logger.warning("EfficientDet-Lite0 could not be loaded: %s", exc)
            notes.append(NOTE_BALL_MODEL_LOAD_FAILED)
    max_frames = max(1, round(max_seconds * fps))
    try:
        try:
            track = track_ball_in_video(path, detector=fused, max_frames=max_frames)
        except Exception:
            if fused is None:
                raise
            logger.exception("Fused ball detector failed; retrying classical only")
            track = track_ball_in_video(path, detector=None, max_frames=max_frames)
    finally:
        if fused is not None:
            fused.close()
    duration = track.frames_read / float(track.fps or fps) if track.frames_read else 0.0
    candidates = detect_video_touch_events(track)
    fusion = fuse_audio_video_events(video_events=candidates, audio_events=[])
    features = extract_session_features(track=track, fusion=fusion, challenge_eval=None, session_duration_s=duration)
    streaks = [int(s) for s in compute_touch_streaks(fusion)]
    ball_frames = sum(1 for pt in track.points if not pt.interpolated)
    ball = {
        "ball_detected": bool(track.points) and ball_frames > 0,
        "total_touches": int(features["total_touches"]),
        "max_streak": int(features["max_streak"]),
        "streaks": streaks,
        "ground_contacts": int(features["ground_bounce_count"]),
        "ball_frames": int(ball_frames),
        "frames_analyzed": int(track.frames_read),
        "detector": "efficientdet+classical" if fused is not None else "classical",
    }
    if not ball["ball_detected"]:
        notes.append(NOTE_NO_BALL)
    elif ball["total_touches"] == 0:
        notes.append(NOTE_NO_TOUCHES)
    return ball


def analyze_video(video_path, *, need_pose: bool = True, need_ball: bool = False) -> dict:
    """Measure a video once. JSON-serializable, compact, never raises."""
    notes: list[str] = []
    try:
        return _analyze(Path(str(video_path)), bool(need_pose), bool(need_ball), notes)
    except Exception:
        logger.exception("Unexpected failure analyzing a skill video")
        result = _empty(notes + [NOTE_POSE_FAILED])
        return result


def _analyze(path: Path, need_pose: bool, need_ball: bool, notes: list[str]) -> dict[str, Any]:
    probe = _probe(path)
    if probe is None:
        return _empty([NOTE_UNREADABLE])
    fps, frame_count, width, _ = probe
    max_seconds = pose_module.MAX_ANALYZED_SECONDS
    result = _empty(notes)
    result["readable"] = True
    result["duration_seconds"] = round(frame_count / fps, 2) if frame_count else 0.0
    result["pose_status"] = POSE_NOT_REQUESTED

    if need_pose:
        model_path = pose_module.pose_model_path()
        extractor = None
        if not model_path.is_file():
            notes.append(NOTE_POSE_MODEL_MISSING)
            result["pose_status"] = POSE_MODEL_UNAVAILABLE
        else:
            try:
                extractor = pose_module.PoseExtractor(model_path)
            except Exception as exc:
                logger.warning("Pose landmarker could not be loaded: %s", exc)
                notes.append(NOTE_POSE_MODEL_LOAD_FAILED)
                result["pose_status"] = POSE_MODEL_UNAVAILABLE
        if extractor is not None:
            try:
                block, frames_read, truncated = _extract_pose(path, fps, max_seconds, extractor)
                analyzed = frames_read / fps if fps else 0.0
                block["analyzed_seconds"] = round(analyzed, 2)
                block["truncated"] = truncated
                result["pose"] = block
                result["pose_status"] = POSE_OK
                result["frames_analyzed"] = block["frames_sampled"]
                if not result["duration_seconds"]:
                    result["duration_seconds"] = round(analyzed, 2)
                if truncated:
                    notes.append(NOTE_TRUNCATED.format(secs=int(max_seconds)))
                if block["frames_detected"] == 0:
                    notes.append(NOTE_NO_PERSON)
                elif block["detected_ratio"] < LOW_PERSON_RATIO:
                    notes.append(NOTE_LOW_PERSON.format(pct=int(round(block["detected_ratio"] * 100))))
            except Exception:
                logger.exception("Pose extraction failed")
                notes.append(NOTE_POSE_FAILED)
                result["pose_status"] = POSE_FAILED
            finally:
                extractor.close()

    if need_ball:
        try:
            ball = _analyze_ball(path, fps, width, max_seconds, notes)
            result["ball"] = ball
            result["ball_status"] = BALL_OK
            if not result["frames_analyzed"]:
                result["frames_analyzed"] = ball["frames_analyzed"]
        except Exception:
            logger.exception("Ball analysis failed")
            notes.append(NOTE_BALL_FAILED)
            result["ball_status"] = BALL_FAILED
    result["notes"] = notes
    return result

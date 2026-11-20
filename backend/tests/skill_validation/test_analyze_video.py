"""S5/S6: `analyze_video` on real files: never raises, reports missing models and empty scenes honestly."""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.football.pipeline import efficientdet_ball_detector
from app.skill_validation import ENGINE_VERSION, analyze_video, evaluate_skill
from app.skill_validation import pose as pose_module
from app.skill_validation.contract import LevelSpec, SkillSpec
from tests.skill_validation import synthetic as syn

ANALYSIS_KEYS = {"engine_version", "readable", "duration_seconds", "frames_analyzed", "pose", "pose_status", "ball",
                 "ball_status", "notes"}
SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "install_vision_models.py"
REAL_MODEL = pose_module.pose_model_path()
requires_model = pytest.mark.skipif(not REAL_MODEL.is_file(), reason="pose_landmarker_full.task not installed")


@pytest.fixture
def empty_scene_video(tmp_path: Path) -> Path:
    """2 s, 320x240, 15 fps: a moving gray square on a dark background, nobody in it."""
    path = tmp_path / "empty.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 15.0, (320, 240))
    assert writer.isOpened()
    for i in range(30):
        frame = np.full((240, 320, 3), 30, dtype=np.uint8)
        cv2.rectangle(frame, (10 + 5 * i, 80), (60 + 5 * i, 130), (160, 160, 160), -1)
        writer.write(frame)
    writer.release()
    return path


@pytest.fixture
def no_pose_model(monkeypatch, tmp_path):
    monkeypatch.setattr(pose_module, "pose_model_path", lambda: tmp_path / "absent-pose.task")


def test_missing_model_returns_no_pose_with_spanish_note(empty_scene_video, no_pose_model):
    analysis = analyze_video(empty_scene_video)
    assert set(analysis) == ANALYSIS_KEYS
    assert analysis["readable"] is True and analysis["engine_version"] == ENGINE_VERSION
    assert analysis["pose"] is None and analysis["pose_status"] == "model_unavailable"
    assert analysis["notes"] == ["El modelo de pose no está instalado; no se pudo analizar el movimiento."]
    assert analysis["duration_seconds"] == pytest.approx(2.0, abs=0.1)
    json.dumps(analysis, allow_nan=False)

    skill = SkillSpec("s", "Hab", 0.0, (
        LevelSpec("l1", 1, "Uno", 10.0, (), reference=syn.analysis(syn.signature(syn.squat))),
    ))
    result = evaluate_skill(skill, analysis)
    assert result["levels"][0]["evaluable"] is False
    assert result["approved"] is False and result["achieved_level"] is None


@pytest.mark.parametrize("kind", ["missing", "corrupt", "directory", "none"])
def test_unreadable_input_never_raises(tmp_path, kind):
    target: object
    if kind == "missing":
        target = tmp_path / "nope.mp4"
    elif kind == "corrupt":
        target = tmp_path / "corrupt.mp4"
        target.write_bytes(b"\x00not a video" * 100)
    elif kind == "directory":
        target = tmp_path
    else:
        target = None
    analysis = analyze_video(target)
    assert set(analysis) == ANALYSIS_KEYS
    assert analysis["readable"] is False and analysis["pose"] is None and analysis["ball"] is None
    assert analysis["notes"] == ["No se pudo leer el video (formato no soportado o archivo dañado)."]
    result = evaluate_skill(SkillSpec("s", "Hab", 0.0, ()), analysis)
    assert result["analysis_complete"] is False and result["score"] == 0.0


def test_ball_analysis_on_empty_scene(empty_scene_video, no_pose_model, monkeypatch, tmp_path):
    monkeypatch.setattr(efficientdet_ball_detector, "efficientdet_model_path", lambda: tmp_path / "absent.tflite")
    analysis = analyze_video(empty_scene_video, need_pose=False, need_ball=True)
    assert analysis["pose_status"] == "not_requested" and analysis["ball_status"] == "ok"
    ball = analysis["ball"]
    assert {"ball_detected", "total_touches", "max_streak", "streaks", "ground_contacts"} <= set(ball)
    assert ball["max_streak"] == 0 and ball["total_touches"] == 0
    json.dumps(analysis, allow_nan=False)


@requires_model
def test_real_model_reports_nobody_in_an_empty_scene(empty_scene_video):
    analysis = analyze_video(empty_scene_video)
    assert analysis["pose_status"] == "ok"
    pose = analysis["pose"]
    assert pose["detected_ratio"] == 0.0 and pose["frames_detected"] == 0
    assert pose["frames_sampled"] == pytest.approx(20, abs=2)  # ~10 fps over 2 s
    assert pose["features"] == pose_module.FEATURE_NAMES
    assert "No se detectó a ninguna persona en el video." in analysis["notes"]
    json.dumps(analysis, allow_nan=False)


@requires_model
def test_real_model_loads():
    extractor = pose_module.PoseExtractor(REAL_MODEL)
    try:
        assert extractor.process(np.zeros((240, 320, 3), dtype=np.uint8), 0) is None
    finally:
        extractor.close()


def test_pose_model_is_pinned_apart_from_face_models():
    spec = importlib.util.spec_from_file_location("install_vision_models_t2", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert set(module.MODELS) == {
        "face_detection_yunet_2023mar.onnx", "face_recognition_sface_2021dec.onnx", "face_landmarker.task",
    }
    url, sha = module.ALL_MODELS[pose_module.POSE_MODEL_FILENAME]
    assert url.startswith("https://storage.googleapis.com/mediapipe-models/pose_landmarker/")
    assert re.fullmatch(r"[0-9a-f]{64}", sha)
    assert pose_module.POSE_MODEL_FILENAME not in module.MODELS

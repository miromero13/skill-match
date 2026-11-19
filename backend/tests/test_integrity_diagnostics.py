"""T11: opt-in numeric diagnostics log (one JSON line per AV window) used to tune thresholds on real sessions."""
import json
import uuid

import numpy as np
import pytest

from app.core.config import Settings, settings
from app.services.integrity import diagnostics
from app.services.integrity.models import (
    AudioObservation, FrameObservation, FrameOcclusion, GazeEvidence, GazeZone, LipSyncResult, WindowObservation,
)
from test_av_missing_evidence import post, window
from test_continuous_supervision import ROOT, empty_scene_models, start_trial  # noqa: F401
from test_evaluation_preflight import isolated_db, scenario  # noqa: F401

FORBIDDEN = {"frames_b64", "image", "audio_samples", "embedding", "voiceprint", "gaze_zone", "occlusion_ref",
             "blendshapes", "landmarks", "mouth_patch", "chunk_rms", "voiced_flags", "zone"}


def build(environment, flag):
    return Settings.model_construct(ENVIRONMENT=environment, INTEGRITY_DIAGNOSTICS_ENABLED=flag)


@pytest.mark.parametrize(("environment", "flag", "expected"), [
    ("production", True, False), ("production", False, False), ("development", False, False),
    ("development", True, True), ("test", True, True), ("staging", True, True),
])
def test_diagnostics_flag_truth_table(environment, flag, expected):
    assert build(environment, flag).integrity_diagnostics_enabled is expected


def test_diagnostics_default_is_off_and_dir_is_under_the_temp_dir():
    import tempfile
    assert Settings.model_fields["INTEGRITY_DIAGNOSTICS_ENABLED"].default is False
    assert Settings.model_fields["INTEGRITY_DIAGNOSTICS_DIR"].get_default(call_default_factory=True).startswith(
        tempfile.gettempdir())


@pytest.fixture
def diag_dir(tmp_path, monkeypatch):
    target = tmp_path / "not-created-yet"
    monkeypatch.setattr(settings, "INTEGRITY_DIAGNOSTICS_DIR", str(target))
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")
    return target


def rich_observation():
    frame = FrameObservation(
        face_count=1, pitch_deg=4.0, yaw_deg=-2.5, gaze_h=0.1, gaze_v=-0.2, blink=False, mouth_open_score=0.3,
        identity_similarity=0.71, frame_delta=3.2, camera_blocked=False,
        blendshapes={f"b{i}": 0.1 for i in range(52)}, landmarks=np.zeros((478, 3)),
        occlusion=FrameOcclusion(face=False, mouth=True, measured=True, signals=("mouth",)),
    )
    audio = AudioObservation(
        rms=0.0123, speech_detected=True, voiced_chunks=30, speakers=1, voice_status="match", voice_similarity=0.62,
        chunk_rms=np.ones(80, dtype=np.float32), voiced_flags=[True] * 80,
    )
    zone = GazeZone(-10, 10, -10, 10, -1, 1, -1, 1)
    return WindowObservation(
        frames=(frame, frame), audio=audio, duration_ms=2400, gaze=GazeEvidence(zone=zone),
        lip_sync=LipSyncResult("synced", 0.7, 0.5, 60, "telemetry"),
    )


def test_record_has_numbers_and_never_the_forbidden_keys():
    record = diagnostics.window_record(rich_observation(), ["MOUTH_OCCLUDED"], uuid.uuid4(), "boca_tapada", 1.0)
    assert record["label"] == "boca_tapada" and record["anomalies"] == ["MOUTH_OCCLUDED"]
    assert record["frames"][0]["pitch_deg"] == 4.0 and record["frames"][0]["occlusion_mouth"] is True
    assert record["audio"]["rms"] == 0.0123 and record["audio"]["voice_similarity"] == 0.62
    assert record["lip_sync"]["correlation"] == 0.7

    def walk(value, path=""):
        if isinstance(value, dict):
            for key, inner in value.items():
                assert key not in FORBIDDEN, path + key
                walk(inner, path + key + ".")
        elif isinstance(value, list):
            assert len(value) <= 12
            for inner in value:
                walk(inner, path)
        else:
            assert not (isinstance(value, str) and len(value) > 40), path

    walk(record)
    assert len(json.dumps(record)) < 4000


@pytest.mark.asyncio
async def test_disabled_writes_nothing_and_creates_no_directory(scenario, empty_scene_models, diag_dir):
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)
    response = await post(client, trial, window(tab, label="normal"))
    assert response.status_code == 200
    assert not diag_dir.exists()


@pytest.mark.asyncio
async def test_enabled_appends_one_line_per_window_with_label(scenario, empty_scene_models, diag_dir, monkeypatch):
    monkeypatch.setattr(settings, "INTEGRITY_DIAGNOSTICS_ENABLED", True)
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)
    for label in ("mirando_abajo", "normal"):
        assert (await post(client, trial, window(tab, label=label))).status_code == 200
    lines = (diag_dir / f"{trial['id']}.jsonl").read_text().splitlines()
    records = [json.loads(line) for line in lines]
    assert [r["label"] for r in records] == ["mirando_abajo", "normal"]
    assert all(isinstance(r["anomalies"], list) and r["window_id"] and r["ts"] for r in records)
    assert not FORBIDDEN & set(records[0]) and not FORBIDDEN & set(records[0]["audio"])
    rows = (await client.get(f"{ROOT}/{trial['id']}/events")).json()["data"]
    assert "mirando_abajo" not in json.dumps(rows)


@pytest.mark.asyncio
@pytest.mark.parametrize("label", ["Normal", "con espacios", "x" * 41, "a/b", ""])
async def test_invalid_label_is_a_422_envelope(scenario, empty_scene_models, diag_dir, label):
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)
    response = await post(client, trial, window(tab, label=label))
    assert response.status_code == 422
    assert set(response.json()) == {"statuscode", "message", "data"} and response.json()["data"] is None


@pytest.mark.asyncio
async def test_write_failure_does_not_fail_the_request(scenario, empty_scene_models, diag_dir, monkeypatch, caplog):
    monkeypatch.setattr(settings, "INTEGRITY_DIAGNOSTICS_ENABLED", True)
    blocker = diag_dir.parent / "blocker"
    blocker.write_text("a file, so the directory cannot be created")
    monkeypatch.setattr(settings, "INTEGRITY_DIAGNOSTICS_DIR", str(blocker / "sub"))
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)
    with caplog.at_level("WARNING"):
        response = await post(client, trial, window(tab, label="normal"))
    assert response.status_code == 200 and response.json()["statuscode"] == 200
    assert any("diagnostics" in message.lower() for message in caplog.messages)

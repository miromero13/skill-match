"""SM-49 continuous audiovisual supervision tests."""
import base64
import uuid
from datetime import datetime, timezone

import numpy as np
import pytest

from app.services.continuous_supervision_service import ContinuousSupervisionService
from test_evaluation_preflight import isolated_db, scenario, endpoint  # noqa: F401

ROOT = "/api/browser-supervision/trials"


def create_dummy_jpeg():
    """Generates a minimal valid JPEG image bytes in memory."""
    import cv2
    img = np.zeros((120, 160, 3), dtype=np.uint8)
    _, buf = cv2.imencode(".jpg", img)
    return "data:image/jpeg;base64," + base64.b64encode(buf).decode("ascii")


class EmptySceneDetector:
    """Injected YuNet stand-in that sees no face (keeps the API tests independent of local weights)."""

    def setInputSize(self, _size):
        pass

    def detect(self, _img):
        return 1, None


@pytest.fixture
def empty_scene_models(monkeypatch):
    monkeypatch.setattr(
        ContinuousSupervisionService, "get_vision_models", staticmethod(lambda: (EmptySceneDetector(), None))
    )
    monkeypatch.setattr(ContinuousSupervisionService, "get_mediapipe_landmarker", classmethod(lambda cls: None))


@pytest.fixture
def no_models_at_all(monkeypatch):
    monkeypatch.setattr(ContinuousSupervisionService, "get_vision_models", staticmethod(lambda: (None, None)))
    monkeypatch.setattr(ContinuousSupervisionService, "get_mediapipe_landmarker", classmethod(lambda cls: None))


async def start_trial(client, tab=None):
    tab = tab or str(uuid.uuid4())
    resp = await client.post(ROOT, json={"tab_id": tab, "accepted": True})
    assert resp.status_code == 200
    return resp.json()["data"], tab


@pytest.mark.asyncio
async def test_av_window_detection_and_ledger_integration(scenario, empty_scene_models):
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)

    window_id = str(uuid.uuid4())
    jpeg_frame = create_dummy_jpeg()

    # Window with 1 dummy frame (no face) and quiet audio with high noise
    noise_audio = [0.25 * ((-1) ** (i % 2)) for i in range(1600)]  # RMS > 0.22

    payload = {
        "tab_id": tab,
        "window_id": window_id,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": 2400,
        "mode": "UNIFIED",
        "frames": [jpeg_frame],
        "audio_samples": noise_audio,
    }

    resp = await client.post(f"{ROOT}/{trial['id']}/av-window", json=payload)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["window_id"] == window_id
    assert "FACE_ABSENT" in data["anomalies"]
    assert "HIGH_NOISE" in data["anomalies"]
    assert len(data["incidents_created"]) >= 2

    # Verify incidents are in the ledger
    ledger_resp = await client.get(f"{ROOT}/{trial['id']}/events")
    assert ledger_resp.status_code == 200
    ledger_data = ledger_resp.json()["data"]
    kinds = [row["kind"] for row in ledger_data]
    assert "FACE_ABSENT" in kinds
    assert "HIGH_NOISE" in kinds


@pytest.mark.asyncio
async def test_av_window_idempotency_retry(scenario, empty_scene_models):
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)

    window_id = str(uuid.uuid4())
    jpeg_frame = create_dummy_jpeg()

    payload = {
        "tab_id": tab,
        "window_id": window_id,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": 2400,
        "mode": "UNIFIED",
        "frames": [jpeg_frame],
        "audio_samples": [],
    }

    resp1 = await client.post(f"{ROOT}/{trial['id']}/av-window", json=payload)
    assert resp1.status_code == 200
    created1 = len(resp1.json()["data"]["incidents_created"])

    # Second call with identical window_id
    resp2 = await client.post(f"{ROOT}/{trial['id']}/av-window", json=payload)
    assert resp2.status_code == 200
    created2 = len(resp2.json()["data"]["incidents_created"])

    assert created1 == created2

    # Check total events in ledger did not double
    ledger_resp = await client.get(f"{ROOT}/{trial['id']}/events")
    assert ledger_resp.json()["count"] == created1


@pytest.mark.asyncio
async def test_av_window_without_vision_models_is_an_incident_not_a_clean_face(scenario, no_models_at_all):
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)
    payload = {
        "tab_id": tab,
        "window_id": str(uuid.uuid4()),
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": 2400,
        "mode": "UNIFIED",
        "frames": [create_dummy_jpeg()],
        "audio_samples": [],
    }
    resp = await client.post(f"{ROOT}/{trial['id']}/av-window", json=payload)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "MODEL_UNAVAILABLE" in data["anomalies"]
    assert data["face_count"] != 1
    assert data["identity_match"] is None
    ledger = await client.get(f"{ROOT}/{trial['id']}/events")
    assert "MODEL_UNAVAILABLE" in [row["kind"] for row in ledger.json()["data"]]


@pytest.mark.asyncio
async def test_av_window_rejected_on_unauthorized_tab(scenario):
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)

    other_tab = str(uuid.uuid4())
    payload = {
        "tab_id": other_tab,
        "window_id": str(uuid.uuid4()),
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": 2400,
        "mode": "UNIFIED",
        "frames": [],
        "audio_samples": [],
    }

    resp = await client.post(f"{ROOT}/{trial['id']}/av-window", json=payload)
    assert resp.status_code == 409


def test_head_pose_down_and_lateral_and_mouth_sync():
    """Verifies downward head tilt, lateral turn, and voice-mouth synchronization."""
    img = np.full((240, 320, 3), 128, dtype=np.uint8)

    class StubDetector:
        def __init__(self, face_row):
            self.face_row = face_row

        def setInputSize(self, _size):
            pass

        def detect(self, _img):
            return 1, np.asarray([self.face_row], dtype=np.float32)

    # 1. Neutral centered face: box(80,40,120,150), eyes(115,95) & (165,95), nose(140,126), mouth(120,155) & (160,155)
    neutral_face = [80, 40, 120, 150, 115, 95, 165, 95, 140, 126, 120, 155, 160, 155, 0.95]
    res_center = ContinuousSupervisionService.analyze_frame_face(
        img, StubDetector(neutral_face), None, None, trial_key="trial-pose-test"
    )
    assert res_center["orientation"] == "CENTER"

    # 1b. Frontal face with higher natural pitch_ratio (~0.59) and nose_mouth_eye_ratio (~0.35) must be CENTER, not DOWN
    frontal_laptop_face = [80, 40, 120, 150, 115, 103, 165, 103, 140, 128, 120, 145.5, 160, 145.5, 0.95]
    res_laptop_center = ContinuousSupervisionService.analyze_frame_face(
        img, StubDetector(frontal_laptop_face), None, None, trial_key="trial-laptop-frontal"
    )
    assert res_laptop_center["orientation"] == "CENTER"

    # 2. Looking down: nose moves closer to mouth (ny=137 vs mouth=153), eyes shift lower in box
    down_face = [80, 45, 120, 145, 115, 108, 165, 108, 140, 137, 120, 153, 160, 153, 0.92]
    res_down = ContinuousSupervisionService.analyze_frame_face(
        img, StubDetector(down_face), None, None, trial_key="trial-pose-test"
    )
    assert res_down["orientation"] == "DOWN"

    # 3. Lateral turn: nose shifts horizontally by >= 0.14 * eye_distance
    side_face = [80, 40, 120, 150, 115, 95, 165, 95, 149, 126, 124, 155, 164, 155, 0.93]
    res_side = ContinuousSupervisionService.analyze_frame_face(
        img, StubDetector(side_face), None, None, trial_key="trial-pose-test"
    )
    assert res_side["orientation"] in ("LEFT", "RIGHT")

    # 4. Mouth movement detection across patches
    static_mouth = (np.full((28, 40), 100.0, dtype=np.float32), np.full(1152, 120.0, dtype=np.float32))
    open_mouth_arr = np.full((28, 40), 100.0, dtype=np.float32)
    open_mouth_arr[8:20, 10:30] = 25.0  # dark open mouth cavity
    moving_mouth = (open_mouth_arr, np.full(1152, 120.0, dtype=np.float32))

    assert ContinuousSupervisionService.compute_mouth_movement([static_mouth, static_mouth, static_mouth]) is False
    assert ContinuousSupervisionService.compute_mouth_movement([static_mouth, moving_mouth, static_mouth]) is True

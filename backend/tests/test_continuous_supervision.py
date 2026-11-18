"""SM-49 continuous audiovisual supervision tests."""
import base64
import uuid
from datetime import datetime, timezone

import numpy as np
import pytest

from test_evaluation_preflight import isolated_db, scenario, endpoint  # noqa: F401

ROOT = "/api/browser-supervision/trials"


def create_dummy_jpeg():
    """Generates a minimal valid JPEG image bytes in memory."""
    # 0xFFD8 starts JPEG, 0xFFD9 ends JPEG
    import cv2
    img = np.zeros((120, 160, 3), dtype=np.uint8)
    _, buf = cv2.imencode(".jpg", img)
    return "data:image/jpeg;base64," + base64.b64encode(buf).decode("ascii")


async def start_trial(client, tab=None):
    tab = tab or str(uuid.uuid4())
    resp = await client.post(ROOT, json={"tab_id": tab, "accepted": True})
    assert resp.status_code == 200
    return resp.json()["data"], tab


@pytest.mark.asyncio
async def test_av_window_detection_and_ledger_integration(scenario):
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)

    window_id = str(uuid.uuid4())
    jpeg_frame = create_dummy_jpeg()

    # Window with 1 dummy frame (no face) and quiet audio with high noise
    noise_audio = [0.25 * ((-1) ** (i % 2)) for i in range(1600)]  # RMS > 0.15

    payload = {
        "tab_id": tab,
        "window_id": window_id,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": 8000,
        "mode": "QUIET",
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
async def test_av_window_idempotency_retry(scenario):
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)

    window_id = str(uuid.uuid4())
    jpeg_frame = create_dummy_jpeg()

    payload = {
        "tab_id": tab,
        "window_id": window_id,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": 8000,
        "mode": "QUIET",
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
async def test_av_window_rejected_on_unauthorized_tab(scenario):
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)

    other_tab = str(uuid.uuid4())
    payload = {
        "tab_id": other_tab,
        "window_id": str(uuid.uuid4()),
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": 8000,
        "mode": "QUIET",
        "frames": [],
        "audio_samples": [],
    }

    resp = await client.post(f"{ROOT}/{trial['id']}/av-window", json=payload)
    assert resp.status_code == 409

"""S8 / S13 (T3): missing or unusable evidence is an incident, never a clean window."""
import base64
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cv2
import numpy as np
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.services.continuous_supervision_service import ContinuousSupervisionService as Service
from test_continuous_supervision import (  # noqa: F401
    ROOT, create_dummy_jpeg, empty_scene_models, start_trial,
)
from test_evaluation_preflight import isolated_db, scenario  # noqa: F401

SAMPLES_2400 = 38_400  # 2.4 s at 16 kHz


def jpeg(width, height):
    ok, buf = cv2.imencode(".jpg", np.zeros((height, width, 3), dtype=np.uint8))
    assert ok
    return base64.b64encode(buf).decode("ascii")


def quiet(n=SAMPLES_2400):
    return [0.0] * n


def assess(frames, audio, duration_ms=2400):
    return Service.assess_window(frames, audio, duration_ms=duration_ms, trial_id=f"t-{uuid.uuid4()}")


def window(tab, frames=None, audio=None, **extra):
    return {"tab_id": tab, "window_id": str(uuid.uuid4()),
            "observed_at": datetime.now(timezone.utc).isoformat(), "duration_ms": 2400, "mode": "UNIFIED",
            "frames": [create_dummy_jpeg()] if frames is None else frames,
            "audio_samples": quiet() if audio is None else audio, **extra}


async def post(client, trial, payload):
    return await client.post(f"{ROOT}/{trial['id']}/av-window", json=payload)


async def kinds(client, trial):
    rows = (await client.get(f"{ROOT}/{trial['id']}/events")).json()["data"]
    return [row["kind"] for row in rows]


def test_empty_frames_are_video_missing_not_a_clean_face(empty_scene_models):
    result = assess([], quiet())
    assert "VIDEO_MISSING" in result["anomalies"]
    assert result["face_count"] == 0
    assert result["head_orientation"] == "UNKNOWN"
    assert result["identity_match"] is None
    assert result["mouth_sync"] is None
    assert "AUDIO_MISSING" not in result["anomalies"]


@pytest.mark.parametrize("frame", ["", "not-base64-@@@", "data:image/jpeg;base64,AAAA",
                                   base64.b64encode(b"\x00" * 64).decode()])
def test_undecodable_frames_are_video_missing(empty_scene_models, frame):
    result = assess([frame, frame], quiet())
    assert "VIDEO_MISSING" in result["anomalies"]
    assert result["face_count"] == 0 and result["head_orientation"] == "UNKNOWN"


def test_oversized_image_is_rejected_before_full_decode(empty_scene_models, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("oversized image must not be fully decoded")

    big = jpeg(4000, 3000)
    monkeypatch.setattr(cv2, "imdecode", forbidden)
    assert Service.decode_frame(big) is None
    result = assess([big], quiet())
    assert "VIDEO_MISSING" in result["anomalies"]


def test_limits_allow_full_hd_in_either_orientation():
    assert Service.decode_frame(jpeg(1920, 1080)) is not None
    assert Service.decode_frame(jpeg(1080, 1920)) is not None
    assert Service.decode_frame(jpeg(1921, 1080)) is None
    assert Service.decode_frame(jpeg(1920, 1081)) is None
    assert Service.decode_frame(jpeg(1081, 1920)) is None


def test_decodable_frame_is_not_video_missing(empty_scene_models):
    result = assess([create_dummy_jpeg()], quiet())
    assert "VIDEO_MISSING" not in result["anomalies"]


@pytest.mark.parametrize("audio", [None, [], quiet(100)])
def test_missing_audio_is_an_incident(empty_scene_models, audio):
    assert "AUDIO_MISSING" in assess([create_dummy_jpeg()], audio)["anomalies"]


@pytest.mark.parametrize("count", [1_600, 28_000, 48_100, 160_000])
def test_audio_length_inconsistent_with_duration_is_an_incident(empty_scene_models, count):
    assert "AUDIO_MISSING" in assess([create_dummy_jpeg()], quiet(count))["anomalies"]


@pytest.mark.parametrize("count", [SAMPLES_2400, 30_000, 47_900])
def test_audio_length_within_tolerance_is_accepted(empty_scene_models, count):
    assert "AUDIO_MISSING" not in assess([create_dummy_jpeg()], quiet(count))["anomalies"]


@pytest.mark.asyncio
async def test_oversized_frame_string_is_a_422_envelope(scenario):
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)
    response = await post(client, trial, window(tab, frames=["A" * 400_001]))
    assert response.status_code == 422
    assert set(response.json()) == {"statuscode", "message", "data"} and response.json()["data"] is None
    assert await kinds(client, trial) == []
    ok = await post(client, trial, window(tab, frames=["A" * 400_000]))
    assert ok.status_code == 200
    assert "VIDEO_MISSING" in ok.json()["data"]["anomalies"]


@pytest.mark.asyncio
async def test_missing_evidence_is_persisted_in_the_ledger(scenario, empty_scene_models):
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)
    response = await post(client, trial, window(tab, frames=[], audio=[]))
    data = response.json()["data"]
    assert {"VIDEO_MISSING", "AUDIO_MISSING"} <= set(data["anomalies"])
    assert {"VIDEO_MISSING", "AUDIO_MISSING"} <= set(await kinds(client, trial))
    assert data["face_count"] == 0 and data["head_orientation"] == "UNKNOWN"


@pytest.mark.asyncio
async def test_complete_window_has_no_missing_evidence_incident(scenario, empty_scene_models):
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)
    data = (await post(client, trial, window(tab))).json()["data"]
    assert not {"VIDEO_MISSING", "AUDIO_MISSING", "WINDOW_GAP"} & set(data["anomalies"])


def clock(monkeypatch):
    from app.services import browser_supervision_service as service
    state = {"now": datetime.now(timezone.utc)}
    monkeypatch.setattr(service, "utcnow", lambda: state["now"])
    return state


@pytest.mark.asyncio
async def test_late_window_records_one_window_gap(scenario, empty_scene_models, monkeypatch):
    client, _, _, _ = scenario
    state = clock(monkeypatch)
    trial, tab = await start_trial(client)
    assert "WINDOW_GAP" not in (await post(client, trial, window(tab))).json()["data"]["anomalies"]
    state["now"] += timedelta(seconds=2)
    assert "WINDOW_GAP" not in (await post(client, trial, window(tab))).json()["data"]["anomalies"]
    state["now"] += timedelta(seconds=10)
    late = (await post(client, trial, window(tab))).json()["data"]
    assert "WINDOW_GAP" in late["anomalies"]
    gap = next(row for row in late["incidents_created"] if row["kind"] == "WINDOW_GAP")
    assert gap["duration_ms"] == 10_000
    state["now"] += timedelta(seconds=2)
    assert "WINDOW_GAP" not in (await post(client, trial, window(tab))).json()["data"]["anomalies"]
    assert (await kinds(client, trial)).count("WINDOW_GAP") == 1


@pytest.mark.asyncio
async def test_heartbeat_records_gap_once_when_windows_stop(scenario, empty_scene_models, monkeypatch):
    client, _, _, _ = scenario
    state = clock(monkeypatch)
    trial, tab = await start_trial(client)
    beat = f"{ROOT}/{trial['id']}/heartbeat"
    assert (await client.post(beat, json={"tab_id": tab})).status_code == 200
    assert "WINDOW_GAP" not in await kinds(client, trial)  # AV never started: nothing to miss
    await post(client, trial, window(tab))
    state["now"] += timedelta(seconds=5)
    assert (await client.post(beat, json={"tab_id": tab})).status_code == 200
    assert "WINDOW_GAP" not in await kinds(client, trial)
    state["now"] += timedelta(seconds=5)
    assert (await client.post(beat, json={"tab_id": tab})).status_code == 200
    assert (await kinds(client, trial)).count("WINDOW_GAP") == 1
    state["now"] += timedelta(seconds=5)
    for _ in range(2):
        assert (await client.post(beat, json={"tab_id": tab})).status_code == 200
    rows = (await client.get(f"{ROOT}/{trial['id']}/events")).json()["data"]
    gaps = [row for row in rows if row["kind"] == "WINDOW_GAP"]
    assert len(gaps) == 1 and gaps[0]["duration_ms"] == 15_000
    # The window that finally arrives closes the same gap instead of adding a second row.
    late = (await post(client, trial, window(tab))).json()["data"]
    assert (await kinds(client, trial)).count("WINDOW_GAP") == 1
    assert "WINDOW_GAP" in late["anomalies"]


def test_alembic_has_a_single_head_that_adds_last_av_window_at():
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).parents[1] / "alembic"))
    script = ScriptDirectory.from_config(config)
    assert len(script.get_heads()) == 1
    head = script.get_revision(script.get_heads()[0])
    assert head.revision == "dbe2f44f08c2"
    # The merge lives in its own empty revision so `downgrade -1` stays unambiguous.
    merge = script.get_revision(head.down_revision)
    assert set(merge.down_revision) == {"c3bea441869b", "ce51f995031a", "f6a39d2c801b"}

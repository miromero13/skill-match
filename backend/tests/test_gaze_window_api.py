"""S5 / S12 / S10 (T6): gaze timestamps and browser telemetry through POST .../av-window."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import update

from gaze_fixtures import eye_points, face_result
from test_av_missing_evidence import post, window  # noqa: F401
from test_av_window_isolation import result, stub  # noqa: F401
from test_browser_supervision import ROOT  # noqa: F401
from test_continuous_supervision import create_dummy_jpeg, start_trial  # noqa: F401
from test_evaluation_preflight import isolated_db, scenario  # noqa: F401
from test_gaze_duration import ScriptedLandmarker, looking

from app.models.browser_supervision import BrowserTrial
from app.services.continuous_supervision_service import ContinuousSupervisionService as Service
from app.services.integrity import frame_analyzer


def telemetry(count=3, **extra):
    return [{"t_ms": 100 * i, "head_pitch": 1.0, "head_yaw": -2.0, "gaze_h": 0.1, "gaze_v": -0.1, "blink": False,
             "face_count": 1, **extra} for i in range(count)]


async def kinds(client, trial):
    rows = (await client.get(f"{ROOT}/{trial['id']}/events?limit=200")).json()["data"]
    return [row["kind"] for row in rows]


@pytest.mark.asyncio
async def test_window_carries_times_telemetry_and_zone_to_the_engine(scenario, monkeypatch):
    client, db, _, _ = scenario
    trial, tab = await start_trial(client)
    zone = {"pitch_min": -9.0, "pitch_max": 13.0, "yaw_min": -13.0, "yaw_max": 13.0, "gaze_h_min": -0.65,
            "gaze_h_max": 0.65, "gaze_v_min": -0.45, "gaze_v_max": 0.55}
    await db.execute(update(BrowserTrial).where(BrowserTrial.id == uuid.UUID(trial["id"])).values(gaze_zone=zone))
    await db.commit()
    calls = []
    stub(monkeypatch, calls=calls)
    observed = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    frames = [create_dummy_jpeg() for _ in range(3)]
    response = await post(client, trial, window(
        tab, frames=frames, observed_at=observed.isoformat(), frame_times_ms=[0, 700, 1500],
        gaze_samples=telemetry(3)))
    assert response.status_code == 200
    kwargs = calls[0]
    assert kwargs["gaze_zone"] == zone
    assert kwargs["frame_times_ms"] == [0, 700, 1500]
    assert kwargs["observed_at_ms"] == int(observed.timestamp() * 1000)
    assert [sample.t_ms for sample in kwargs["gaze_samples"]] == [0, 100, 200]


@pytest.mark.asyncio
async def test_legacy_window_without_gaze_fields_is_still_valid(scenario, monkeypatch):
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)
    calls = []
    stub(monkeypatch, calls=calls)
    assert (await post(client, trial, window(tab))).status_code == 200
    assert calls[0]["gaze_zone"] is None and calls[0]["frame_times_ms"] is None
    assert list(calls[0]["gaze_samples"]) == []


@pytest.mark.parametrize(
    "extra",
    [
        {"frames": [create_dummy_jpeg()] * 2, "frame_times_ms": [0]},  # not aligned with the frames
        {"frames": [create_dummy_jpeg()] * 2, "frame_times_ms": [900, 100]},  # going backwards
        {"frames": [create_dummy_jpeg()], "frame_times_ms": [-1]},
        {"frames": [create_dummy_jpeg()], "frame_times_ms": [2401]},  # after the window ended
        {"frames": [], "frame_times_ms": [0]},
        {"gaze_samples": telemetry(61)},  # at most 60 per window
        {"gaze_samples": [{**telemetry(1)[0], "t_ms": 2401}]},
        {"gaze_samples": [{**telemetry(1)[0], "t_ms": -1}]},
        {"gaze_samples": telemetry(2, t_ms=100)},  # same instant twice
        {"gaze_samples": [{**telemetry(1)[0], "t_ms": 0}, {**telemetry(1)[0], "t_ms": 10}]},  # faster than 30 fps
        {"gaze_samples": [{**telemetry(1)[0], "face_count": 11}]},
        {"gaze_samples": [{**telemetry(1)[0], "gaze_h": 9.0}]},
        {"gaze_samples": [{**telemetry(1)[0], "head_pitch": 181.0}]},
        {"gaze_samples": [{**telemetry(1)[0], "extra": 1}]},
        {"gaze_samples": [{k: v for k, v in telemetry(1)[0].items() if k != "blink"}]},
    ],
)
@pytest.mark.asyncio
async def test_invalid_gaze_fields_are_a_422_envelope_and_store_nothing(scenario, monkeypatch, extra):
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)
    calls = []
    stub(monkeypatch, calls=calls)
    response = await post(client, trial, window(tab, **extra))
    assert response.status_code == 422
    assert set(response.json()) == {"statuscode", "message", "data"} and response.json()["data"] is None
    assert calls == [] and await kinds(client, trial) == []


@pytest.mark.parametrize("anomaly", ["GAZE_AWAY", "HEAD_POSE_UP", "CLIENT_MISMATCH"])
@pytest.mark.asyncio
async def test_new_gaze_incidents_are_ledger_rows_only(scenario, monkeypatch, anomaly):
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)
    stub(monkeypatch, anomaly)
    response = await post(client, trial, window(tab))
    assert response.status_code == 200 and response.json()["data"]["anomalies"] == [anomaly]
    rows = (await client.get(f"{ROOT}/{trial['id']}/events")).json()["data"]
    assert [row["kind"] for row in rows] == [anomaly]
    assert set(rows[0]) == {"event_id", "kind", "observed_at", "duration_ms", "sequence", "received_at"}


@pytest.fixture
def scripted(monkeypatch):
    def install(kinds_):
        landmarker = ScriptedLandmarker([looking(kind) for kind in kinds_])
        monkeypatch.setattr(Service, "get_vision_models", staticmethod(lambda: (None, None)))
        monkeypatch.setattr(frame_analyzer, "get_landmarker", lambda: landmarker)
        return landmarker

    return install


def eight(tab, observed, **extra):
    return window(tab, frames=[create_dummy_jpeg() for _ in range(8)], observed_at=observed.isoformat(),
                  frame_times_ms=[i * 300 for i in range(8)], **extra)


@pytest.mark.asyncio
async def test_a_run_across_two_windows_is_recorded_in_the_second_one(scenario, scripted):
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)
    scripted(["in"] * 5 + ["eyes"] * 3 + ["eyes"] * 2 + ["in"] * 6)
    start = datetime.now(timezone.utc)
    first = await post(client, trial, eight(tab, start))
    assert first.status_code == 200 and first.json()["data"]["anomalies"] == []
    second = await post(client, trial, eight(tab, start + timedelta(milliseconds=2400)))
    assert second.json()["data"]["anomalies"] == ["GAZE_AWAY_DOWN"]
    assert await kinds(client, trial) == ["GAZE_AWAY_DOWN"]


@pytest.mark.asyncio
async def test_the_trial_zone_is_what_decides_what_is_away(scenario, scripted):
    client, db, _, _ = scenario
    trial, tab = await start_trial(client)
    scripted(["in", "in"] + ["eyes"] * 4 + ["in", "in"])
    wide = {"pitch_min": -9.0, "pitch_max": 13.0, "yaw_min": -13.0, "yaw_max": 13.0, "gaze_h_min": -0.65,
            "gaze_h_max": 0.65, "gaze_v_min": -0.45, "gaze_v_max": 1.5}
    await db.execute(update(BrowserTrial).where(BrowserTrial.id == uuid.UUID(trial["id"])).values(gaze_zone=wide))
    await db.commit()
    response = await post(client, trial, eight(tab, datetime.now(timezone.utc)))
    assert response.json()["data"]["anomalies"] == []


@pytest.mark.asyncio
async def test_a_browser_that_contradicts_the_server_is_a_client_mismatch_incident(scenario, scripted):
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)
    scripted(["in", "in"] + ["down"] * 4 + ["in", "in"])
    lying = [{"t_ms": 66 * i, "head_pitch": 0.0, "head_yaw": 0.0, "gaze_h": 0.0, "gaze_v": 0.0, "blink": False,
              "face_count": 1} for i in range(36)]
    response = await post(client, trial, eight(tab, datetime.now(timezone.utc), gaze_samples=lying))
    assert response.status_code == 200
    assert response.json()["data"]["anomalies"] == ["HEAD_POSE_DOWN", "CLIENT_MISMATCH"]
    assert set(await kinds(client, trial)) == {"HEAD_POSE_DOWN", "CLIENT_MISMATCH"}

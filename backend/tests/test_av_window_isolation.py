"""S13 (T4): AV inference runs off the event loop and outside the row lock; AV rows are capped."""
import asyncio
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest
from sqlalchemy import func, insert, select, update

from app.models.browser_supervision import BrowserIncident, BrowserTrial
from app.services import browser_supervision_service as service
from app.services.continuous_supervision_service import ContinuousSupervisionService as Service
from test_av_missing_evidence import clock, kinds, post, window  # noqa: F401
from test_browser_supervision import LOCKED, ROOT, body, event  # noqa: F401
from test_continuous_supervision import empty_scene_models, start_trial  # noqa: F401
from test_evaluation_preflight import isolated_db, scenario  # noqa: F401


def result(*anomalies):
    return {"face_count": 1, "head_orientation": "CENTER", "identity_match": None, "speech_detected": False,
            "mouth_moving": False, "mouth_sync": None, "multiple_speakers": False, "noise_level": 0.0,
            "anomalies": list(anomalies)}


def stub(monkeypatch, *anomalies, calls=None):
    def fake(**kwargs):
        if calls is not None:
            calls.append(kwargs)
        return result(*anomalies)

    monkeypatch.setattr(Service, "assess_window", staticmethod(fake))


def at(base, seconds):
    return (base + timedelta(seconds=seconds)).isoformat()


async def rows(client, trial):
    return (await client.get(f"{ROOT}/{trial['id']}/events?limit=200")).json()["data"]


@pytest.mark.asyncio
async def test_inference_runs_in_a_worker_thread_and_never_blocks_the_loop(scenario, monkeypatch):
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)
    seen = {}

    def slow(**_kwargs):
        seen["thread"] = threading.current_thread()
        time.sleep(0.5)
        return result()

    monkeypatch.setattr(Service, "assess_window", staticmethod(slow))
    ticks = 0
    done = asyncio.Event()

    async def ticker():
        nonlocal ticks
        while not done.is_set():
            await asyncio.sleep(0.02)
            ticks += 1

    task = asyncio.create_task(ticker())
    response = await post(client, trial, window(tab))
    done.set()
    await task
    assert response.status_code == 200
    assert seen["thread"] is not threading.main_thread()
    assert seen["thread"].name.startswith("av-inference")
    assert ticks >= 10  # a blocked loop would have produced at most one tick


@pytest.mark.asyncio
async def test_no_transaction_or_row_lock_is_held_during_inference(scenario, monkeypatch):
    client, db, _, _ = scenario
    trial, tab = await start_trial(client)
    seen = {}

    def probe(**_kwargs):
        seen["in_transaction"] = db.in_transaction()
        return result()

    monkeypatch.setattr(Service, "assess_window", staticmethod(probe))
    assert (await post(client, trial, window(tab))).status_code == 200
    assert seen == {"in_transaction": False}


@pytest.mark.asyncio
async def test_lease_lost_during_inference_is_409_and_persists_nothing(scenario, monkeypatch):
    client, db, _, _ = scenario
    trial, tab = await start_trial(client)
    loop = asyncio.get_running_loop()

    async def expire():
        await db.execute(update(BrowserTrial).where(BrowserTrial.id == uuid.UUID(trial["id"]))
                         .values(lease_until=datetime.now(timezone.utc) - timedelta(seconds=1)))
        await db.commit()

    def losing(**_kwargs):
        asyncio.run_coroutine_threadsafe(expire(), loop).result(10)
        return result("HIGH_NOISE", "FACE_ABSENT")

    monkeypatch.setattr(Service, "assess_window", staticmethod(losing))
    response = await post(client, trial, window(tab))
    assert response.status_code == 409 and response.json() == body(LOCKED, status=409)
    assert await rows(client, trial) == []
    stored = (await db.execute(select(BrowserTrial.event_count, BrowserTrial.last_av_window_at)
                               .where(BrowserTrial.id == uuid.UUID(trial["id"])))).one()
    assert tuple(stored) == (0, None)


@pytest.mark.asyncio
async def test_lease_is_verified_before_inference(scenario, monkeypatch):
    client, _, _, _ = scenario
    trial, _ = await start_trial(client)
    calls = []
    stub(monkeypatch, "HIGH_NOISE", calls=calls)
    response = await post(client, trial, window(str(uuid.uuid4())))
    assert response.status_code == 409 and calls == []


@pytest.mark.asyncio
async def test_consecutive_noise_windows_extend_one_episode(scenario, monkeypatch):
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)
    stub(monkeypatch, "HIGH_NOISE")
    base = datetime.now(timezone.utc)
    first = (await post(client, trial, window(tab, observed_at=at(base, 0)))).json()["data"]
    created = first["incidents_created"]
    assert [row["kind"] for row in created] == ["HIGH_NOISE"] and created[0]["duration_ms"] == 2400
    second = (await post(client, trial, window(tab, observed_at=at(base, 2.4)))).json()["data"]
    assert [row["kind"] for row in second["incidents_created"]] == ["HIGH_NOISE"]
    assert second["incidents_created"][0]["sequence"] == created[0]["sequence"]
    third = (await post(client, trial, window(tab, observed_at=at(base, 4.8)))).json()["data"]
    assert "HIGH_NOISE" in third["anomalies"]
    stored = await rows(client, trial)
    assert len(stored) == 1 and stored[0]["sequence"] == 1
    assert stored[0]["duration_ms"] == 7200
    # A much later window starts a new episode.
    await post(client, trial, window(tab, observed_at=at(base, 60)))
    assert [(row["kind"], row["sequence"]) for row in await rows(client, trial)] == [("HIGH_NOISE", 1), ("HIGH_NOISE", 2)]


@pytest.mark.asyncio
async def test_episodes_merge_per_kind_only(scenario, monkeypatch):
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)
    base = datetime.now(timezone.utc)
    stub(monkeypatch, "HIGH_NOISE")
    await post(client, trial, window(tab, observed_at=at(base, 0)))
    stub(monkeypatch, "HIGH_NOISE", "FACE_ABSENT")
    await post(client, trial, window(tab, observed_at=at(base, 2.4)))
    stored = await rows(client, trial)
    assert sorted(row["kind"] for row in stored) == ["FACE_ABSENT", "HIGH_NOISE"]
    assert {row["kind"]: row["duration_ms"] for row in stored} == {"HIGH_NOISE": 4800, "FACE_ABSENT": 2400}


@pytest.mark.asyncio
async def test_reposting_windows_is_idempotent_even_after_merges(scenario, monkeypatch):
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)
    stub(monkeypatch, "HIGH_NOISE")
    base = datetime.now(timezone.utc)
    windows = [window(tab, observed_at=at(base, offset)) for offset in (0, 2.4, 60)]
    for payload in windows:
        assert (await post(client, trial, payload)).status_code == 200
    before = await rows(client, trial)
    assert [row["duration_ms"] for row in before] == [4800, 2400]
    for payload in windows:  # replay every window, including merged and superseded ones
        again = await post(client, trial, payload)
        assert again.status_code == 200 and len(again.json()["data"]["incidents_created"]) == 1
    assert await rows(client, trial) == before


@pytest.mark.asyncio
async def test_av_rows_beyond_the_minute_cap_are_not_inserted(scenario, monkeypatch):
    client, _, _, _ = scenario
    state = clock(monkeypatch)
    trial, tab = await start_trial(client)
    monkeypatch.setattr(service, "AV_ROWS_PER_MINUTE", 3)
    stub(monkeypatch, "HIGH_NOISE")
    base = datetime.now(timezone.utc)
    last = None
    for index in range(5):
        state["now"] += timedelta(seconds=2)
        last = await post(client, trial, window(tab, observed_at=at(base, index * 60)))
        assert last.status_code == 200
    assert len(await rows(client, trial)) == 3
    assert "HIGH_NOISE" in last.json()["data"]["anomalies"] and last.json()["data"]["incidents_created"] == []
    for _ in range(8):  # a minute passes; heartbeats keep the lease and note the interruption
        state["now"] += timedelta(seconds=8)
        assert (await client.post(f"{ROOT}/{trial['id']}/heartbeat", json={"tab_id": tab})).status_code == 200
    again = await post(client, trial, window(tab, observed_at=at(base, 600)))
    assert "HIGH_NOISE" in [row["kind"] for row in again.json()["data"]["incidents_created"]]
    assert sorted(row["kind"] for row in await rows(client, trial)) == ["HIGH_NOISE"] * 4 + ["WINDOW_GAP"]


@pytest.mark.asyncio
async def test_av_rows_beyond_the_trial_cap_are_not_inserted(scenario, monkeypatch):
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)
    monkeypatch.setattr(service, "AV_ROWS_PER_TRIAL", 2)
    stub(monkeypatch, "HIGH_NOISE")
    base = datetime.now(timezone.utc)
    for index in range(4):
        response = await post(client, trial, window(tab, observed_at=at(base, index * 60)))
        assert response.status_code == 200
        assert response.json()["data"]["anomalies"] == ["HIGH_NOISE"]
    assert len(await rows(client, trial)) == 2


@pytest.mark.asyncio
async def test_av_rows_never_starve_browser_events(scenario, monkeypatch):
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)
    stub(monkeypatch, "HIGH_NOISE")
    base = datetime.now(timezone.utc)
    for index in range(130):
        assert (await post(client, trial, window(tab, observed_at=at(base, index * 60)))).status_code == 200
    assert len(await rows(client, trial)) == 120  # default AV cap per minute
    events = [event("COPY") for _ in range(50)]
    for offset in range(0, 200, 50):
        batch = events if offset == 0 else [event("PASTE") for _ in range(50)]
        response = await client.post(f"{ROOT}/{trial['id']}/events", json={"tab_id": tab, "events": batch})
        assert response.status_code == 200
    over = await client.post(f"{ROOT}/{trial['id']}/events", json={"tab_id": tab, "events": [event()]})
    assert over.status_code == 429  # the browser cap itself is unchanged


@pytest.mark.asyncio
async def test_total_browser_cap_ignores_av_rows(scenario):
    client, db, _, _ = scenario
    trial, tab = await start_trial(client)
    trial_id = uuid.UUID(trial["id"])
    old = datetime.now(timezone.utc) - timedelta(days=1)
    await db.execute(insert(BrowserIncident), [
        {"trial_id": trial_id, "event_id": uuid.uuid4(), "sequence": index + 1, "kind": "HIGH_NOISE",
         "observed_at": old, "received_at": old, "duration_ms": 0} for index in range(9_990)])
    await db.execute(update(BrowserTrial).where(BrowserTrial.id == trial_id).values(event_count=9_990))
    await db.commit()
    response = await client.post(f"{ROOT}/{trial['id']}/events", json={"tab_id": tab, "events": [event("COPY") for _ in range(20)]})
    assert response.status_code == 200 and response.json()["data"]["event_count"] == 10_010
    browser = await db.scalar(select(func.count()).select_from(BrowserIncident).where(
        BrowserIncident.trial_id == trial_id, BrowserIncident.kind == "COPY"))
    assert browser == 20


def test_landmarker_detect_is_serialized_across_threads():
    state = {"active": 0, "peak": 0}

    class Landmarker:
        def detect(self, _image):
            state["active"] += 1
            state["peak"] = max(state["peak"], state["active"])
            time.sleep(0.03)
            state["active"] -= 1
            return type("Result", (), {"face_landmarks": [], "face_blendshapes": [],
                                       "facial_transformation_matrixes": []})()

    image = np.zeros((48, 64, 3), dtype=np.uint8)
    landmarker = Landmarker()
    threads = [threading.Thread(target=Service._analyze_with_mediapipe, args=(image, "t", landmarker))
               for _ in range(6)]
    [thread.start() for thread in threads]
    [thread.join() for thread in threads]
    assert state["peak"] == 1


def test_per_trial_state_is_only_touched_under_the_state_lock(monkeypatch):
    class Recording:
        def __init__(self):
            self.inner = threading.RLock()
            self.depth = 0
            self.entries = 0

        def __enter__(self):
            self.inner.acquire()
            self.depth += 1
            self.entries += 1

        def __exit__(self, *_args):
            self.depth -= 1
            self.inner.release()

    lock = Recording()
    monkeypatch.setattr(Service, "_state_lock", lock)

    class Guarded(dict):
        def _check(self):
            assert lock.depth > 0, "per-trial state touched without the lock"

        def get(self, *args):
            self._check()
            return super().get(*args)

        def __contains__(self, key):
            self._check()
            return super().__contains__(key)

        def __setitem__(self, key, value):
            self._check()
            super().__setitem__(key, value)

        def __len__(self):
            self._check()
            return super().__len__()

    from collections import OrderedDict

    class GuardedOrdered(Guarded, OrderedDict):
        pass

    monkeypatch.setattr(Service, "_trial_baselines", GuardedOrdered())
    monkeypatch.setattr(Service, "_trial_audio_state", GuardedOrdered())
    metrics = {"pitch_deg": 0.0, "yaw_deg": 0.0, "eye_look_down": 0.0, "pitch_ratio": 0.5,
               "nose_mouth_eye_ratio": 0.4}
    Service._get_or_update_baseline("trial", metrics, True)
    Service._get_or_update_baseline("trial", metrics, True)
    audio = np.zeros(38_400, dtype=np.float32)
    Service._detect_multi_speaker_or_background_media(audio, [True] * 10, "trial")
    Service.analyze_audio([0.0] * 3_200, trial_key="trial")
    assert lock.entries >= 4

"""T9b / item 5: a valid recent calibration seeds a new supervision trial; nothing else does (written with the code)."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from tests.test_evaluation_preflight import CONSENT, endpoint, isolated_db, scenario  # noqa: F401
from tests.test_calibration_audio import consented
from app.core.security import create_access_token
from app.models import User, UserRole
from app.models.calibration import CalibrationChallenge
from app.services.continuous_supervision_service import ContinuousSupervisionService as Supervision
from app.services.evaluation_calibration_service import CalibrationSeed, EvaluationCalibrationService as Service
from test_continuous_supervision import start_trial  # noqa: F401
from test_integrity_calibration import http_body

URL = "/liveness/verify-identity"


async def calibrate(scenario, monkeypatch):
    client, offer, root, challenge, good = await consented(scenario, monkeypatch)
    assert (await client.post(root + URL, json=http_body(good, challenge["id"]))).status_code == 200
    db = scenario[1]
    row = (await db.execute(select(CalibrationChallenge).where(CalibrationChallenge.id == uuid.UUID(challenge["id"])))).scalar_one()
    return row


@pytest.mark.asyncio
async def test_a_valid_calibration_gives_zone_voiceprint_ambient_floor_and_reference(scenario, monkeypatch):
    row = await calibrate(scenario, monkeypatch)
    _, db, user, _ = scenario
    seed = await Service.valid_seed(db, user)
    assert isinstance(seed, CalibrationSeed)
    assert seed.gaze_zone.to_dict() == row.gaze_zone and seed.voiceprint == row.voiceprint
    assert seed.ambient_rms == pytest.approx(row.voiceprint["ambient_rms"]) and seed.occlusion_ref == row.occlusion_ref


@pytest.mark.asyncio
async def test_a_trial_started_after_a_valid_calibration_is_seeded(scenario, monkeypatch):
    row = await calibrate(scenario, monkeypatch)
    client, db, _, _ = scenario
    trial, tab = await start_trial(client)
    assert trial["gaze_zone"] == row.gaze_zone and trial["voice_enrolled"] is True
    assert "embedding" not in str(trial) and "voiceprint" not in trial
    from app.models.browser_supervision import BrowserTrial
    stored = (await db.execute(select(BrowserTrial).where(BrowserTrial.id == uuid.UUID(trial["id"])))).scalar_one()
    assert stored.voiceprint == row.voiceprint and stored.gaze_zone == row.gaze_zone
    assert Supervision._trial_tracks[trial["id"]]["occlusion_ref"] == row.occlusion_ref


@pytest.mark.asyncio
async def test_without_a_calibration_the_trial_starts_unseeded_and_its_own_endpoints_remain(scenario):
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)
    assert trial["gaze_zone"] is None and trial["voice_enrolled"] is False
    assert trial["id"] not in Supervision._trial_tracks
    from test_browser_supervision import ROOT
    assert (await client.post(f"{ROOT}/{trial['id']}/gaze-calibration", json={"tab_id": tab, "points": []})).status_code == 422


@pytest.mark.asyncio
async def test_an_expired_calibration_does_not_seed(scenario, monkeypatch):
    row = await calibrate(scenario, monkeypatch)
    client, db, user, _ = scenario
    row.consumed_at = datetime.now(timezone.utc) - timedelta(hours=13)
    await db.commit()
    assert await Service.valid_seed(db, user) is None
    trial, _ = await start_trial(client)
    assert trial["gaze_zone"] is None and trial["voice_enrolled"] is False


@pytest.mark.asyncio
async def test_a_calibration_just_inside_the_age_limit_still_seeds(scenario, monkeypatch):
    row = await calibrate(scenario, monkeypatch)
    _, db, user, _ = scenario
    row.consumed_at = datetime.now(timezone.utc) - timedelta(hours=11, minutes=59)
    await db.commit()
    assert await Service.valid_seed(db, user) is not None


@pytest.mark.asyncio
async def test_another_members_calibration_never_seeds(scenario, monkeypatch):
    await calibrate(scenario, monkeypatch)
    client, db, _, _ = scenario
    other = User(email=f"{uuid.uuid4()}@example.test", full_name="Other", role=UserRole.MEMBER,
                 biometric_embedding="[0.1]", biometric_face_hash="enrolled-reference")  # even the same enrollment hash
    db.add(other)
    await db.commit()
    assert await Service.valid_seed(db, other) is None
    client.headers["Authorization"] = f"Bearer {create_access_token(subject=str(other.id), role=other.role.value)}"
    trial, _ = await start_trial(client)
    assert trial["gaze_zone"] is None and trial["voice_enrolled"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("spoil", ["enrollment", "checks", "zone", "voiceprint", "reference", "garbage_voiceprint", "garbage_zone"])
async def test_a_calibration_that_is_not_complete_for_the_current_enrollment_does_not_seed(scenario, monkeypatch, spoil):
    row = await calibrate(scenario, monkeypatch)
    _, db, user, _ = scenario
    if spoil == "enrollment":
        user.biometric_face_hash = "re-enrolled-face"
    elif spoil == "checks":
        row.checks = {**row.checks, "voiceprint": False}
    elif spoil == "zone":
        row.gaze_zone = None
    elif spoil == "voiceprint":
        row.voiceprint = None
    elif spoil == "reference":
        row.occlusion_ref = None
    elif spoil == "garbage_voiceprint":
        row.voiceprint = {"embedding": "nope"}
    else:
        row.gaze_zone = {"pitch_min": 1.0}
    await db.commit()
    assert await Service.valid_seed(db, user) is None


@pytest.mark.asyncio
async def test_the_latest_valid_calibration_wins_and_an_open_trial_is_not_reseeded(scenario, monkeypatch):
    client, db, user, _ = scenario
    trial, tab = await start_trial(client)  # started before any calibration
    await calibrate(scenario, monkeypatch)
    again, _ = await start_trial(client, tab)
    assert again["id"] == trial["id"] and again["gaze_zone"] is None  # an existing trial keeps its own calibration

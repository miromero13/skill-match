"""S5 / T6: POST /api/browser-supervision/trials/{id}/gaze-calibration stores the per-trial screen zone."""
import uuid

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models import User, UserRole
from app.models.browser_supervision import BrowserTrial
from app.services.continuous_supervision_service import ContinuousSupervisionService as Service
from app.services.integrity.models import FrameBatch, FrameObservation
from test_browser_supervision import LOCKED, ROOT, body  # noqa: F401
from test_continuous_supervision import create_dummy_jpeg, start_trial  # noqa: F401
from test_evaluation_preflight import isolated_db, scenario  # noqa: F401

TARGETS = ("CENTER", "TOP_LEFT", "TOP_RIGHT", "BOTTOM_LEFT", "BOTTOM_RIGHT")
VALUES = {
    "CENTER": (0.0, 0.0, 0.0, 0.0),
    "TOP_LEFT": (-4.0, -8.0, -0.5, -0.3),
    "TOP_RIGHT": (-4.0, 8.0, 0.5, -0.3),
    "BOTTOM_LEFT": (8.0, -8.0, -0.5, 0.4),
    "BOTTOM_RIGHT": (8.0, 8.0, 0.5, 0.4),
}
SAVED = "Zona de mirada calibrada."


def obs(pitch, yaw, gaze_h, gaze_v):
    return FrameObservation(face_count=1, pitch_deg=pitch, yaw_deg=yaw, gaze_h=gaze_h, gaze_v=gaze_v)


def payload(tab, frames=3, targets=TARGETS):
    return {"tab_id": tab, "points": [{"target": name, "frames": [create_dummy_jpeg()] * frames}
                                       for name in targets]}


@pytest.fixture
def measured(monkeypatch):
    """Stands in for the vision models: each target's frames measure as the scripted observation."""
    script = {"values": dict(VALUES), "override": {}}

    def fake(cls, frames_by_target):
        out = {}
        for name, frames in frames_by_target.items():
            if name in script["override"]:
                out[name] = script["override"][name]
            else:
                out[name] = FrameBatch(frames=tuple(obs(*script["values"][name]) for _ in frames))
        return out

    monkeypatch.setattr(Service, "analyze_gaze_targets", classmethod(fake))
    return script


async def calibrate(client, trial, body_):
    return await client.post(f"{ROOT}/{trial['id']}/gaze-calibration", json=body_)


@pytest.mark.asyncio
async def test_calibration_stores_the_zone_and_the_trial_exposes_it(scenario, measured):
    client, db, _, _ = scenario
    trial, tab = await start_trial(client)
    assert trial["gaze_zone"] is None
    response = await calibrate(client, trial, payload(tab))
    assert response.status_code == 200
    assert response.json()["message"] == SAVED
    zone = response.json()["data"]["zone"]
    assert zone["pitch_min"] == pytest.approx(-9.0) and zone["pitch_max"] == pytest.approx(13.0)
    assert zone["yaw_min"] == pytest.approx(-13.0) and zone["gaze_h_max"] == pytest.approx(0.65)
    assert response.json()["data"]["frames_used"] == 15
    stored = (await db.execute(select(BrowserTrial.gaze_zone).where(BrowserTrial.id == uuid.UUID(trial["id"])))
              ).scalar_one()
    assert stored == zone
    reread = (await client.get(f"{ROOT}/{trial['id']}")).json()["data"]
    assert reread["gaze_zone"] == zone


@pytest.mark.asyncio
async def test_recalibration_replaces_the_zone(scenario, measured):
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)
    first = (await calibrate(client, trial, payload(tab))).json()["data"]["zone"]
    measured["values"]["BOTTOM_RIGHT"] = (20.0, 20.0, 0.9, 0.9)
    second = (await calibrate(client, trial, payload(tab))).json()["data"]["zone"]
    assert second["pitch_max"] > first["pitch_max"]
    assert (await client.get(f"{ROOT}/{trial['id']}")).json()["data"]["gaze_zone"] == second


@pytest.mark.parametrize(
    ("override", "message"),
    [
        (FrameBatch(frames=(FrameObservation(face_count=0),) * 3),
         "No pudimos ver tu rostro en todos los puntos. Ubicate frente a la cámara con buena luz y repetí la calibración."),
        (FrameBatch(frames=(FrameObservation(face_count=2),) * 3),
         "Se detectó más de una persona durante la calibración. Tiene que estar solo tu rostro en cámara."),
    ],
)
@pytest.mark.asyncio
async def test_unmeasurable_faces_are_a_400_in_spanish_and_store_nothing(scenario, measured, override, message):
    client, db, _, _ = scenario
    trial, tab = await start_trial(client)
    measured["override"]["TOP_LEFT"] = override
    response = await calibrate(client, trial, payload(tab))
    assert response.status_code == 400
    assert response.json() == body(message, status=400)
    assert (await client.get(f"{ROOT}/{trial['id']}")).json()["data"]["gaze_zone"] is None


@pytest.mark.asyncio
async def test_targets_that_cannot_be_told_apart_are_a_400(scenario, measured):
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)
    measured["values"] = {name: (0.0, 0.0, 0.0, 0.0) for name in TARGETS}
    response = await calibrate(client, trial, payload(tab))
    assert response.status_code == 400
    assert response.json() == body(
        "No pudimos distinguir hacia dónde mirabas. Mirá cada punto moviendo los ojos o la cabeza hacia esa "
        "esquina y repetí la calibración.", status=400)
    assert (await client.get(f"{ROOT}/{trial['id']}")).json()["data"]["gaze_zone"] is None


@pytest.mark.asyncio
async def test_missing_vision_model_is_503_not_a_clean_calibration(scenario, measured):
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)
    measured["override"]["CENTER"] = FrameBatch(model_unavailable=True)
    response = await calibrate(client, trial, payload(tab))
    assert response.status_code == 503
    assert response.json() == body("El análisis de mirada no está disponible en este momento. Reintentá más tarde.",
                                   status=503)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p["points"].pop(),  # a missing target
        lambda p: p["points"].append(dict(p["points"][0])),  # a repeated target
        lambda p: p["points"][0].update(target="MIDDLE"),  # an unknown target
        lambda p: p["points"][0].update(frames=[]),  # no frames
        lambda p: p["points"][0].update(frames=[create_dummy_jpeg()] * 7),  # too many frames
        lambda p: p.update(extra=1),
    ],
)
@pytest.mark.asyncio
async def test_invalid_payload_is_a_422_envelope(scenario, measured, mutate):
    client, _, _, _ = scenario
    trial, tab = await start_trial(client)
    data = payload(tab)
    mutate(data)
    response = await calibrate(client, trial, data)
    assert response.status_code == 422
    assert set(response.json()) == {"statuscode", "message", "data"} and response.json()["data"] is None
    assert (await client.get(f"{ROOT}/{trial['id']}")).json()["data"]["gaze_zone"] is None


@pytest.mark.asyncio
async def test_foreign_members_and_admins_get_the_404_and_other_tabs_the_lease_conflict(scenario, measured):
    client, db, _, _ = scenario
    trial, tab = await start_trial(client)
    conflict = await calibrate(client, trial, payload(str(uuid.uuid4())))
    assert conflict.status_code == 409 and conflict.json() == body(LOCKED, status=409)
    original = client.headers["Authorization"]
    for role in (UserRole.MEMBER, UserRole.ADMIN):
        other = User(email=f"{uuid.uuid4()}@example.test", full_name="Other", role=role)
        db.add(other)
        await db.commit()
        client.headers["Authorization"] = f"Bearer {create_access_token(subject=str(other.id), role=role.value)}"
        response = await calibrate(client, trial, payload(tab))
        assert response.status_code == 404
        assert response.json() == body("Recurso no encontrado", status=404)
    client.headers["Authorization"] = original
    assert (await client.get(f"{ROOT}/{trial['id']}")).json()["data"]["gaze_zone"] is None

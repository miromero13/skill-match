"""SM-43 public contracts; disposable schema, never application records."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import create_access_token
from app.models import User, UserRole
from test_evaluation_preflight import isolated_db, scenario, endpoint  # noqa: F401

ROOT = "/api/browser-supervision/trials"
STARTED = "Sesión de prueba preparada. No inicia un examen ni consume intentos."
SAVED = "Incidentes de prueba guardados."
LOCKED = "Esta prueba está activa en otra pestaña o perdió su autorización. Esperá hasta 20 segundos y reintentá."


def body(message, data=None, status=200):
    return {"statuscode": status, "message": message, "data": data}


def event(kind="PASTE", **extra):
    return {"event_id": str(uuid.uuid4()), "kind": kind,
            "observed_at": datetime.now(timezone.utc).isoformat(), **extra}


async def start(client, tab=None):
    tab = tab or str(uuid.uuid4())
    response = await client.post(ROOT, json={"tab_id": tab, "accepted": True})
    assert response.status_code == 200
    assert response.json()["message"] == STARTED
    assert set(response.json()) == {"statuscode", "message", "data"}
    return response.json()["data"], tab


async def ledger(client, trial):
    response = await client.get(f"{ROOT}/{trial['id']}/events")
    assert response.status_code == 200
    assert response.json()["message"] == "Bitácora de prueba recuperada."
    return response.json()


@pytest.mark.asyncio
async def test_trial_records_once_paginates_and_never_spends(scenario):
    client, _, _, offer = scenario
    before = (await client.get(endpoint(offer, "preflight"))).json()
    trial, tab = await start(client)
    same, _ = await start(client, tab)
    assert trial["id"] == same["id"] and trial["mode"] == "TRIAL"
    first = event("AWAY", duration_ms=0)
    second = event("RETURN", duration_ms=1200)
    payload = {"tab_id": tab, "events": [first, second]}
    for _ in range(2):
        response = await client.post(f"{ROOT}/{trial['id']}/events", json=payload)
        assert response.status_code == 200
        assert response.json() == body(SAVED, {"accepted_ids": [first["event_id"], second["event_id"]], "event_count": 2})
    log = await ledger(client, trial)
    assert log["count"] == 2
    assert [row["kind"] for row in log["data"]] == ["AWAY", "RETURN"]
    assert log["data"][1]["duration_ms"] == 1200
    assert all(row["received_at"] for row in log["data"])
    page = await client.get(f"{ROOT}/{trial['id']}/events?after=1&limit=1")
    assert page.json()["count"] == 2 and len(page.json()["data"]) == 1
    assert page.json()["data"][0]["sequence"] == 2
    assert (await client.get(endpoint(offer, "preflight"))).json() == before


@pytest.mark.asyncio
async def test_foreign_anonymous_and_admin_cannot_mutate_or_read(scenario):
    client, db, _, _ = scenario
    trial, tab = await start(client)
    original = client.headers["Authorization"]
    for role in [UserRole.MEMBER, UserRole.ADMIN]:
        other = User(email=f"{uuid.uuid4()}@example.test", full_name="Other", role=role)
        db.add(other)
        await db.commit()
        client.headers["Authorization"] = f"Bearer {create_access_token(subject=str(other.id), role=role.value)}"
        for method, suffix, payload in [("GET", "", None), ("GET", "/events", None),
                                        ("POST", "/events", {"tab_id": tab, "events": [event()]}),
                                        ("POST", "/heartbeat", {"tab_id": tab}),
                                        ("POST", "/close", {"tab_id": tab})]:
            response = await client.request(method, f"{ROOT}/{trial['id']}{suffix}", json=payload)
            assert response.status_code == 404
            assert response.json() == body("Recurso no encontrado", status=404)
    del client.headers["Authorization"]
    response = await client.post(ROOT, json={"tab_id": tab, "accepted": True})
    assert response.status_code == 401
    assert response.json() == body("Encabezado de autorización ausente o con formato inválido (se requiere 'Bearer <token>').", status=401)
    client.headers["Authorization"] = original
    assert (await ledger(client, trial))["count"] == 0


@pytest.mark.asyncio
async def test_second_tab_lease_release_and_closed_session(scenario):
    client, _, _, _ = scenario
    trial, tab = await start(client)
    other = str(uuid.uuid4())
    response = await client.post(ROOT, json={"tab_id": other, "accepted": True})
    assert response.status_code == 409 and response.json() == body(LOCKED, status=409)
    for action in ["events", "heartbeat", "close", "release"]:
        payload = {"tab_id": other}
        if action == "events":
            payload["events"] = [event()]
        response = await client.post(f"{ROOT}/{trial['id']}/{action}", json=payload)
        assert response.status_code == 409 and response.json() == body(LOCKED, status=409)
    response = await client.post(f"{ROOT}/{trial['id']}/release", json={"tab_id": tab})
    assert response.status_code == 200
    resumed, _ = await start(client, other)
    assert resumed["id"] == trial["id"]
    closed = await client.post(f"{ROOT}/{trial['id']}/close", json={"tab_id": other})
    assert closed.status_code == 200 and closed.json()["data"]["closed_at"] is not None
    rejected = await client.post(f"{ROOT}/{trial['id']}/events", json={"tab_id": other, "events": [event()]})
    assert rejected.status_code == 409
    assert (await ledger(client, trial))["count"] == 0


@pytest.mark.asyncio
async def test_expired_lease_can_be_claimed_but_old_tab_cannot_write(scenario, monkeypatch):
    from app.services import browser_supervision_service as service
    client, _, _, _ = scenario
    trial, tab = await start(client)
    later = datetime.now(timezone.utc) + timedelta(seconds=21)
    monkeypatch.setattr(service, "utcnow", lambda: later)
    resumed, other = await start(client)
    assert resumed["id"] == trial["id"]
    response = await client.post(f"{ROOT}/{trial['id']}/heartbeat", json={"tab_id": tab})
    assert response.status_code == 409
    assert (await client.post(f"{ROOT}/{trial['id']}/heartbeat", json={"tab_id": other})).status_code == 200


@pytest.mark.asyncio
async def test_invalid_conflicting_and_oversized_batches_leave_ledger_unchanged(scenario):
    client, _, _, _ = scenario
    trial, tab = await start(client)
    path = f"{ROOT}/{trial['id']}/events"
    first = event()
    assert (await client.post(path, json={"tab_id": tab, "events": [first]})).status_code == 200
    for events in [[{**first, "kind": "COPY"}], [event(), {**first, "kind": "COPY"}]]:
        response = await client.post(path, json={"tab_id": tab, "events": events})
        assert response.status_code == 409
        assert response.json() == body("Un identificador de incidente ya existe con otro contenido.", status=409)
    for events in [[], [event() for _ in range(51)], [event(clipboard="private")],
                   [event("UNKNOWN")], [event(duration_ms=-1)], [event(duration_ms=86400001)],
                   [event(observed_at="2026-01-01T00:00:00")]]:
        response = await client.post(path, json={"tab_id": tab, "events": events})
        assert response.status_code == 422
        assert set(response.json()) == {"statuscode", "message", "data"} and response.json()["data"] is None
    assert (await ledger(client, trial))["count"] == 1


@pytest.mark.asyncio
async def test_fixed_rate_limit_allows_retries_and_no_partial_batch(scenario):
    client, _, _, _ = scenario
    trial, tab = await start(client)
    path = f"{ROOT}/{trial['id']}/events"
    events = [event() for _ in range(200)]
    for offset in range(0, 200, 50):
        assert (await client.post(path, json={"tab_id": tab, "events": events[offset:offset + 50]})).status_code == 200
    assert (await client.post(path, json={"tab_id": tab, "events": events[:50]})).status_code == 200
    response = await client.post(path, json={"tab_id": tab, "events": [event()]} )
    assert response.status_code == 429
    assert response.json() == body("Límite de incidentes de prueba alcanzado. Esperá antes de reenviar.", status=429)
    assert (await ledger(client, trial))["count"] == 200


@pytest.mark.asyncio
async def test_consent_and_trial_expiry_never_start_an_exam(scenario, monkeypatch):
    from app.services import browser_supervision_service as service
    client, _, _, offer = scenario
    before = (await client.get(endpoint(offer, "preflight"))).json()
    for payload in [{"tab_id": str(uuid.uuid4()), "accepted": False},
                    {"tab_id": "invalid", "accepted": True},
                    {"tab_id": str(uuid.uuid4()), "accepted": True, "mode": "EXAM"}]:
        response = await client.post(ROOT, json=payload)
        assert response.status_code == 422 and response.json()["data"] is None
    trial, tab = await start(client)
    now = datetime.now(timezone.utc) + timedelta(hours=24, seconds=1)
    monkeypatch.setattr(service, "utcnow", lambda: now)
    rejected = await client.post(f"{ROOT}/{trial['id']}/events", json={"tab_id": tab, "events": [event()]})
    assert rejected.status_code == 409 and rejected.json() == body(LOCKED, status=409)
    renewed, _ = await start(client)
    assert renewed["id"] != trial["id"]
    assert (await ledger(client, trial))["count"] == 0
    assert (await client.get(endpoint(offer, "preflight"))).json() == before


@pytest.mark.asyncio
async def test_total_limit_rejects_without_changing_count(scenario, monkeypatch):
    from app.services import browser_supervision_service as service
    client, _, _, _ = scenario
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(service, "utcnow", lambda: now)
    trial, tab = await start(client)
    path = f"{ROOT}/{trial['id']}/events"
    last_batch = []
    for index in range(200):
        if index % 4 == 0:
            now += timedelta(seconds=61)
            await start(client, tab)
        last_batch = [event() for _ in range(50)]
        response = await client.post(path, json={"tab_id": tab, "events": last_batch})
        assert response.status_code == 200
        assert response.json()["data"]["event_count"] == (index + 1) * 50
    now += timedelta(seconds=61)
    await start(client, tab)
    duplicate = await client.post(path, json={"tab_id": tab, "events": last_batch})
    assert duplicate.status_code == 200
    response = await client.post(path, json={"tab_id": tab, "events": [event()]})
    assert response.status_code == 429
    assert response.json() == body("Límite de incidentes de prueba alcanzado. Esperá antes de reenviar.", status=429)
    assert (await ledger(client, trial))["count"] == 10000

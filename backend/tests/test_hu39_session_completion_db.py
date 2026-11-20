"""HU-39 PostgreSQL/API integration tests (TDD - Red Phase).

Verifies the end-to-end database transactions, row-level locking, HTTP status codes,
security by obfuscation (404), dual confirmation completion, and boundaries with HU-40/HU-42.
"""

# Nested async contexts keep seeded-data cleanup and client/DB lifetimes explicit.
# ruff: noqa: SIM117

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import delete, select

from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.main import create_application
from app.models.catalog import Category, Skill
from app.models.exchange_session import ExchangeSession
from app.models.match import Match
from app.models.teaching_skill import TeachingSkill
from app.models.user import User, UserRole
from app.models.user_learning_skill import UserLearningSkill

pytestmark = pytest.mark.asyncio(loop_scope="session")


def headers_for(user: User) -> dict[str, str]:
    token = create_access_token(str(user.id), UserRole.MEMBER.value)
    return {"Authorization": f"Bearer {token}"}


def assert_envelope(response: httpx.Response, statuscode: int) -> dict:
    assert response.status_code == statuscode, (
        f"Expected {statuscode}, got {response.status_code}: {response.text}"
    )
    payload = response.json()
    assert payload["statuscode"] == statuscode
    assert isinstance(payload["message"], str) and payload["message"].strip()
    assert "data" in payload
    assert "error" not in payload
    return payload


@asynccontextmanager
async def seeded_accepted_session(*, modality: str = "VIRTUAL", ended: bool = True):
    """Seed an isolated accepted session for testing completion flows."""
    suffix = uuid4().hex
    async with AsyncSessionLocal() as db:
        category = Category(name=f"HU-39-{suffix}", slug=f"hu-39-{suffix}")
        instructor = User(
            email=f"instructor-{suffix}@example.invalid",
            full_name="Instructor HU-39",
            role=UserRole.MEMBER,
            timezone="America/La_Paz",
        )
        learner = User(
            email=f"learner-{suffix}@example.invalid",
            full_name="Learner HU-39",
            role=UserRole.MEMBER,
            timezone="America/La_Paz",
        )
        outsider = User(
            email=f"outsider-{suffix}@example.invalid",
            full_name="Outsider HU-39",
            role=UserRole.MEMBER,
            timezone="America/La_Paz",
        )
        db.add_all([category, instructor, learner, outsider])
        await db.flush()

        skill = Skill(
            name=f"Skill HU-39 {suffix}",
            slug=f"skill-hu-39-{suffix}",
            category_id=category.id,
            is_active=True,
        )
        db.add(skill)
        await db.flush()

        offer = TeachingSkill(
            user_id=instructor.id,
            skill_id=skill.id,
            declared_level="INTERMEDIATE",
            years_of_experience=2,
            accepts_points=False,
        )
        interest = UserLearningSkill(user_id=learner.id, skill_id=skill.id)
        first_id, second_id = sorted([instructor.id, learner.id])
        match = Match(
            member_a_id=first_id,
            member_b_id=second_id,
            status="confirmed",
        )
        db.add_all([offer, interest, match])
        await db.flush()

        now = datetime.now(UTC)
        if ended:
            # Session occurred in the past (already ended)
            starts_at = now - timedelta(hours=2)
            ends_at = now - timedelta(hours=1)
        else:
            # Session is in the future (not ended yet)
            starts_at = now + timedelta(days=1)
            ends_at = starts_at + timedelta(minutes=60)

        session = ExchangeSession(
            match_id=match.id,
            teaching_skill_id=offer.id,
            created_by_id=learner.id,
            instructor_id=instructor.id,
            learner_id=learner.id,
            starts_at=starts_at,
            ends_at=ends_at,
            timezone="America/La_Paz",
            modality=modality,
            status="ACCEPTED",
            is_free=True,
        )
        db.add(session)
        await db.commit()

        for item in (instructor, learner, outsider, session):
            await db.refresh(item)

        seed = {
            "instructor": instructor,
            "learner": learner,
            "outsider": outsider,
            "session": session,
            "match": match,
            "skill": skill,
            "category": category,
        }

    try:
        yield seed
    finally:
        async with AsyncSessionLocal() as cleanup:
            await cleanup.execute(delete(Match).where(Match.id == match.id))
            await cleanup.execute(
                delete(User).where(User.id.in_([instructor.id, learner.id, outsider.id]))
            )
            await cleanup.execute(delete(Skill).where(Skill.id == skill.id))
            await cleanup.execute(delete(Category).where(Category.id == category.id))
            await cleanup.commit()


async def test_confirm_session_returns_404_for_outsider():
    """An outsider member attempting to confirm receives 404 Obfuscation."""
    app = create_application()
    async with seeded_accepted_session(ended=True) as seed:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            resp = await client.post(
                f"/api/sessions/{seed['session'].id}/confirm",
                headers=headers_for(seed["outsider"]),
                json={
                    "request_key": str(uuid4()),
                    "actual_minutes": 60,
                    "topics": ["Testing outsider isolation"],
                },
            )
            payload = assert_envelope(resp, 404)
            assert (
                "recurso no encontrado" in payload["message"].lower()
                or "not found" in payload["message"].lower()
            )


async def test_confirm_session_rejected_before_ends_at():
    """Attempting to confirm a session that has not ended yet returns 409 Conflict."""
    app = create_application()
    async with seeded_accepted_session(ended=False) as seed:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            resp = await client.post(
                f"/api/sessions/{seed['session'].id}/confirm",
                headers=headers_for(seed["learner"]),
                json={
                    "request_key": str(uuid4()),
                    "actual_minutes": 60,
                    "topics": ["Premature confirmation"],
                },
            )
            payload = assert_envelope(resp, 409)
            assert (
                "todavía no puede confirmarse" in payload["message"]
                or "no ha finalizado" in payload["message"].lower()
            )


async def test_confirm_session_first_confirmation_keeps_accepted():
    """First confirmation succeeds, leaves session as ACCEPTED, and notes counterpart pending."""
    app = create_application()
    async with (
        seeded_accepted_session(ended=True) as seed,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client,
    ):
        resp = await client.post(
            f"/api/sessions/{seed['session'].id}/confirm",
            headers=headers_for(seed["learner"]),
            json={
                "request_key": str(uuid4()),
                "actual_minutes": 60,
                "topics": ["First step of dual confirmation"],
            },
        )
        payload = assert_envelope(resp, 200)
        data = payload["data"]
        assert data["status"] == "ACCEPTED"
        assert data["my_confirmation"] is True
        assert data["counterpart_confirmation"] is False
        assert data["actual_minutes"] == 60
        assert data["completed_at"] is None


async def test_confirm_session_second_confirmation_completes_session():
    """Second matching confirmation transitions session atomically to COMPLETED."""
    app = create_application()
    async with seeded_accepted_session(ended=True) as seed:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            # 1. Learner confirms
            resp1 = await client.post(
                f"/api/sessions/{seed['session'].id}/confirm",
                headers=headers_for(seed["learner"]),
                json={
                    "request_key": str(uuid4()),
                    "actual_minutes": 60,
                    "topics": ["Full session"],
                },
            )
            assert_envelope(resp1, 200)

            # 2. Instructor confirms with matching minutes
            resp2 = await client.post(
                f"/api/sessions/{seed['session'].id}/confirm",
                headers=headers_for(seed["instructor"]),
                json={
                    "request_key": str(uuid4()),
                    "actual_minutes": 60,
                    "topics": ["Full session counterpart"],
                },
            )
            payload2 = assert_envelope(resp2, 200)
            data2 = payload2["data"]
            assert data2["status"] == "COMPLETED"
            assert data2["my_confirmation"] is True
            assert data2["counterpart_confirmation"] is True
            assert data2["actual_minutes"] == 60
            assert data2["completed_at"] is not None

        # Verify DB state directly
        async with AsyncSessionLocal() as db:
            refreshed = (
                await db.execute(
                    select(ExchangeSession).where(ExchangeSession.id == seed["session"].id)
                )
            ).scalar_one()
            assert refreshed.status == "COMPLETED"
            assert refreshed.actual_minutes == 60
            assert refreshed.completed_at is not None


async def test_confirm_session_mismatched_minutes_returns_409():
    """Second confirmation with mismatched actual_minutes returns 409 and leaves session ACCEPTED."""
    app = create_application()
    async with seeded_accepted_session(ended=True) as seed:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            # 1. Learner confirms 60 min
            await client.post(
                f"/api/sessions/{seed['session'].id}/confirm",
                headers=headers_for(seed["learner"]),
                json={
                    "request_key": str(uuid4()),
                    "actual_minutes": 60,
                    "topics": ["Topic 1"],
                },
            )

            # 2. Instructor confirms 45 min -> Mismatch
            resp2 = await client.post(
                f"/api/sessions/{seed['session'].id}/confirm",
                headers=headers_for(seed["instructor"]),
                json={
                    "request_key": str(uuid4()),
                    "actual_minutes": 45,
                    "topics": ["Topic 1"],
                },
            )
            payload = assert_envelope(resp2, 409)
            assert "coincidir" in payload["message"].lower()

        # Verify session is still ACCEPTED
        async with AsyncSessionLocal() as db:
            refreshed = (
                await db.execute(
                    select(ExchangeSession).where(ExchangeSession.id == seed["session"].id)
                )
            ).scalar_one()
            assert refreshed.status == "ACCEPTED"


async def test_confirm_session_idempotent_replay():
    """Replaying the exact same confirmation with equal request_key is idempotent."""
    app = create_application()
    key = str(uuid4())
    async with (
        seeded_accepted_session(ended=True) as seed,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client,
    ):
        req = {
            "request_key": key,
            "actual_minutes": 60,
            "topics": ["Idempotent test"],
        }
        resp1 = await client.post(
            f"/api/sessions/{seed['session'].id}/confirm",
            headers=headers_for(seed["learner"]),
            json=req,
        )
        assert_envelope(resp1, 200)

        resp2 = await client.post(
            f"/api/sessions/{seed['session'].id}/confirm",
            headers=headers_for(seed["learner"]),
            json=req,
        )
        assert_envelope(resp2, 200)


async def test_report_noshow_records_auditable_incident():
    """Reporting no-show after ends_at creates an auditable report without altering balances."""
    app = create_application()
    key = str(uuid4())
    async with seeded_accepted_session(ended=True) as seed:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            resp = await client.post(
                f"/api/sessions/{seed['session'].id}/report-noshow",
                headers=headers_for(seed["learner"]),
                json={
                    "request_key": key,
                    "reason": "El instructor no se presento a la reunion virtual pautada.",
                },
            )
            payload = assert_envelope(resp, 200)
            data = payload["data"]
            assert data["session_id"] == str(seed["session"].id)
            assert data["absent_user_id"] == str(seed["instructor"].id)
            assert data["status"] == "PROCESSED"

            # HU-40 processes the attendance incident without locking the account.
            async with AsyncSessionLocal() as db:
                inst = (
                    await db.execute(select(User).where(User.id == seed["instructor"].id))
                ).scalar_one()
                assert inst.is_active is True


async def test_presence_pin_is_stable_and_hidden_from_outsiders():
    """A participant can reload the same PIN while an outsider receives 404."""
    app = create_application()
    async with seeded_accepted_session(modality="PRESENCIAL", ended=True) as seed:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            url = f"/api/sessions/{seed['session'].id}/presence-pin"
            first = await client.get(url, headers=headers_for(seed["instructor"]))
            second = await client.get(url, headers=headers_for(seed["instructor"]))
            outsider = await client.get(url, headers=headers_for(seed["outsider"]))

            first_data = assert_envelope(first, 200)["data"]
            second_data = assert_envelope(second, 200)["data"]
            assert first_data["presence_pin"].isdigit()
            assert len(first_data["presence_pin"]) == 4
            assert second_data["presence_pin"] == first_data["presence_pin"]
            assert_envelope(outsider, 404)


async def test_invalid_presence_pin_attempts_persist_and_lock_at_five():
    """Failed requests preserve the brute-force counter and lock the fifth try."""
    app = create_application()
    async with seeded_accepted_session(modality="PRESENCIAL", ended=True) as seed:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            pin_response = await client.get(
                f"/api/sessions/{seed['session'].id}/presence-pin",
                headers=headers_for(seed["instructor"]),
            )
            valid_pin = assert_envelope(pin_response, 200)["data"]["presence_pin"]
            invalid_pin = "0000" if valid_pin != "0000" else "1111"

            for _ in range(5):
                response = await client.post(
                    f"/api/sessions/{seed['session'].id}/confirm",
                    headers=headers_for(seed["learner"]),
                    json={
                        "request_key": str(uuid4()),
                        "actual_minutes": 60,
                        "topics": ["PIN security regression"],
                        "presence_pin": invalid_pin,
                    },
                )
                assert_envelope(response, 422)

            locked = await client.post(
                f"/api/sessions/{seed['session'].id}/confirm",
                headers=headers_for(seed["learner"]),
                json={
                    "request_key": str(uuid4()),
                    "actual_minutes": 60,
                    "topics": ["PIN security regression"],
                    "presence_pin": valid_pin,
                },
            )
            assert_envelope(locked, 409)


async def test_future_session_does_not_consume_presence_pin_attempts():
    """A premature confirmation is rejected before validating or burning a PIN."""
    app = create_application()
    async with seeded_accepted_session(modality="PRESENCIAL", ended=False) as seed:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            url = f"/api/sessions/{seed['session'].id}/presence-pin"
            created = await client.get(url, headers=headers_for(seed["instructor"]))
            assert assert_envelope(created, 200)["data"]["attempt_count"] == 0

            premature = await client.post(
                f"/api/sessions/{seed['session'].id}/confirm",
                headers=headers_for(seed["learner"]),
                json={
                    "request_key": str(uuid4()),
                    "actual_minutes": 60,
                    "topics": ["Premature PIN attempt"],
                    "presence_pin": "0000",
                },
            )
            assert_envelope(premature, 409)

            unchanged = await client.get(url, headers=headers_for(seed["instructor"]))
            assert assert_envelope(unchanged, 200)["data"]["attempt_count"] == 0


async def test_contradictory_noshow_report_is_rejected():
    """Both participants cannot mark each other absent for the same session."""
    app = create_application()
    async with (
        seeded_accepted_session(ended=True) as seed,
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as client,
    ):
        first = await client.post(
            f"/api/sessions/{seed['session'].id}/report-noshow",
            headers=headers_for(seed["learner"]),
            json={
                "request_key": str(uuid4()),
                "reason": "El instructor no se presento a la sesion acordada.",
            },
        )
        assert_envelope(first, 200)

        contradictory = await client.post(
            f"/api/sessions/{seed['session'].id}/report-noshow",
            headers=headers_for(seed["instructor"]),
            json={
                "request_key": str(uuid4()),
                "reason": "El aprendiz no se presento a la sesion acordada.",
            },
        )
        assert_envelope(contradictory, 409)

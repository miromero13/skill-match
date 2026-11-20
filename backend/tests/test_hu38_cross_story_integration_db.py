"""PostgreSQL/API contracts for the HU-38 cross-story integration phase."""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import delete, func, select

from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.main import create_application
from app.models.catalog import Category, Skill
from app.models.exchange_session import ExchangeSession, WeeklySessionQuota
from app.models.match import Match
from app.models.teaching_skill import TeachingSkill
from app.models.user import User, UserRole
from app.models.user_availability import UserAvailability
from app.models.user_learning_skill import UserLearningSkill
from app.models.wallet import PointTransaction, Wallet

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _headers(user: User) -> dict[str, str]:
    token = create_access_token(str(user.id), UserRole.MEMBER.value)
    return {"Authorization": f"Bearer {token}"}


def _assert_envelope(response: httpx.Response, statuscode: int) -> dict:
    assert response.status_code == statuscode, response.text
    payload = response.json()
    assert payload["statuscode"] == statuscode
    assert isinstance(payload["message"], str) and payload["message"].strip()
    assert "data" in payload
    assert "error" not in payload
    return payload


def _payload(seed: dict, start: datetime, *, payment_method: str) -> dict[str, str]:
    return {
        "match_id": str(seed["match"].id),
        "teaching_skill_id": str(seed["offer"].id),
        "instructor_id": str(seed["instructor"].id),
        "starts_at": start.isoformat(),
        "ends_at": (start + timedelta(minutes=60)).isoformat(),
        "timezone": seed["learner"].timezone,
        "modality": "VIRTUAL",
        "payment_method": payment_method,
    }


@asynccontextmanager
async def _seeded_integration(*, balance: int = 100, quota_used: int = 2):
    suffix = uuid4().hex
    async with AsyncSessionLocal() as db:
        category = Category(name=f"HU-38-X-{suffix}", slug=f"hu-38-x-{suffix}")
        instructor = User(
            email=f"instructor-x-{suffix}@example.invalid",
            full_name="Instructor integración HU-38",
            role=UserRole.MEMBER,
            timezone="America/La_Paz",
        )
        learner = User(
            email=f"learner-x-{suffix}@example.invalid",
            full_name="Learner integración HU-38",
            role=UserRole.MEMBER,
            timezone="America/La_Paz",
        )
        outsider = User(
            email=f"outsider-x-{suffix}@example.invalid",
            full_name="Outsider integración HU-38",
            role=UserRole.MEMBER,
            timezone="America/La_Paz",
        )
        db.add_all([category, instructor, learner, outsider])
        await db.flush()

        skill = Skill(
            name=f"Skill integración {suffix}",
            slug=f"skill-integration-{suffix}",
            category_id=category.id,
            is_active=True,
        )
        db.add(skill)
        await db.flush()
        offer = TeachingSkill(
            user_id=instructor.id,
            skill_id=skill.id,
            declared_level="ADVANCED",
            years_of_experience=3,
            accepts_points=True,
            hourly_points_rate=50,
        )
        interest = UserLearningSkill(user_id=learner.id, skill_id=skill.id)
        member_a, member_b = sorted([instructor.id, learner.id])
        match = Match(member_a_id=member_a, member_b_id=member_b, status="confirmed")
        availability = [
            UserAvailability(
                user_id=user.id,
                day_of_week=day,
                start_time="00:00",
                end_time="23:30",
                is_enabled=True,
                modality="BOTH",
            )
            for user in (instructor, learner)
            for day in range(7)
        ]
        db.add_all([offer, interest, match, *availability])
        await db.flush()

        future = (datetime.now(UTC) + timedelta(days=3)).replace(
            hour=12, minute=0, second=0, microsecond=0
        )
        local_week = (future - timedelta(days=future.weekday())).date()
        db.add_all(
            [
                WeeklySessionQuota(
                    user_id=learner.id,
                    week_start=local_week,
                    used=quota_used,
                ),
                Wallet(user_id=learner.id, balance=balance, escrow_balance=0),
            ]
        )
        await db.commit()
        for item in (category, skill, offer, instructor, learner, outsider, match):
            await db.refresh(item)
        seed = {
            "category": category,
            "skill": skill,
            "offer": offer,
            "instructor": instructor,
            "learner": learner,
            "outsider": outsider,
            "match": match,
            "future": future,
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


async def test_third_session_reserves_points_atomically() -> None:
    async with _seeded_integration(balance=100) as seed:
        app = create_application()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/sessions",
                headers=_headers(seed["learner"]),
                json=_payload(seed, seed["future"], payment_method="POINTS"),
            )
            data = _assert_envelope(response, 201)["data"]
            assert data["is_free"] is False
            assert data["points_required"] == 50
            assert data["payment_state"] == "RESERVED"

        async with AsyncSessionLocal() as db:
            wallet = await db.get(Wallet, seed["learner"].id)
            assert wallet.balance == 50
            assert wallet.escrow_balance == 50


async def test_paid_creation_with_insufficient_balance_is_atomic() -> None:
    async with _seeded_integration(balance=0) as seed:
        app = create_application()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/sessions",
                headers=_headers(seed["learner"]),
                json=_payload(seed, seed["future"], payment_method="POINTS"),
            )
            _assert_envelope(response, 400)

        async with AsyncSessionLocal() as db:
            count = await db.scalar(
                select(func.count(ExchangeSession.id)).where(
                    ExchangeSession.match_id == seed["match"].id
                )
            )
            assert count == 0
            wallet = await db.get(Wallet, seed["learner"].id)
            assert wallet.balance == 0
            assert wallet.escrow_balance == 0


async def test_concurrent_paid_creation_cannot_spend_same_balance_twice() -> None:
    async with _seeded_integration(balance=50) as seed:
        app = create_application()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            responses = await asyncio.gather(
                client.post(
                    "/api/sessions",
                    headers=_headers(seed["learner"]),
                    json=_payload(seed, seed["future"], payment_method="POINTS"),
                ),
                client.post(
                    "/api/sessions",
                    headers=_headers(seed["learner"]),
                    json=_payload(
                        seed,
                        seed["future"] + timedelta(hours=2),
                        payment_method="POINTS",
                    ),
                ),
            )
            assert sorted(response.status_code for response in responses) == [201, 400]

        async with AsyncSessionLocal() as db:
            wallet = await db.get(Wallet, seed["learner"].id)
            assert wallet.balance == 0
            assert wallet.escrow_balance == 50
            sessions = await db.scalar(
                select(func.count(ExchangeSession.id)).where(
                    ExchangeSession.match_id == seed["match"].id
                )
            )
            assert sessions == 1


async def test_rejection_refunds_reserved_escrow_exactly_once() -> None:
    async with _seeded_integration(balance=50) as seed:
        async with AsyncSessionLocal() as db:
            session = ExchangeSession(
                match_id=seed["match"].id,
                teaching_skill_id=seed["offer"].id,
                created_by_id=seed["learner"].id,
                instructor_id=seed["instructor"].id,
                learner_id=seed["learner"].id,
                starts_at=seed["future"],
                ends_at=seed["future"] + timedelta(minutes=60),
                timezone="America/La_Paz",
                modality="VIRTUAL",
                status="PENDING",
                is_free=False,
                points_required=50,
                payment_state="RESERVED",
            )
            wallet = await db.get(Wallet, seed["learner"].id)
            wallet.escrow_balance = 50
            db.add(session)
            await db.commit()
            await db.refresh(session)
            session_id = session.id

        app = create_application()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            first = await client.patch(
                f"/api/sessions/{session_id}/status",
                headers=_headers(seed["instructor"]),
                json={"status": "REJECTED"},
            )
            _assert_envelope(first, 200)
            replay = await client.patch(
                f"/api/sessions/{session_id}/status",
                headers=_headers(seed["instructor"]),
                json={"status": "REJECTED"},
            )
            _assert_envelope(replay, 200)

        async with AsyncSessionLocal() as db:
            wallet = await db.get(Wallet, seed["learner"].id)
            session = await db.get(ExchangeSession, session_id)
            assert wallet.balance == 100
            assert wallet.escrow_balance == 0
            assert session.payment_state == "REFUNDED"


async def test_timely_cancellation_refunds_reserved_escrow_exactly_once() -> None:
    async with _seeded_integration(balance=50) as seed:
        async with AsyncSessionLocal() as db:
            session = ExchangeSession(
                match_id=seed["match"].id,
                teaching_skill_id=seed["offer"].id,
                created_by_id=seed["learner"].id,
                instructor_id=seed["instructor"].id,
                learner_id=seed["learner"].id,
                starts_at=seed["future"],
                ends_at=seed["future"] + timedelta(minutes=60),
                timezone="America/La_Paz",
                modality="VIRTUAL",
                status="ACCEPTED",
                is_free=False,
                points_required=50,
                payment_state="RESERVED",
            )
            wallet = await db.get(Wallet, seed["learner"].id)
            wallet.escrow_balance = 50
            db.add(session)
            await db.commit()
            await db.refresh(session)
            session_id = session.id

        app = create_application()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            for _ in range(2):
                _assert_envelope(
                    await client.post(
                        f"/api/sessions/{session_id}/cancel",
                        headers=_headers(seed["learner"]),
                        json={
                            "cancellation_reason": "Imprevisto comunicado con anticipación suficiente."
                        },
                    ),
                    200,
                )

        async with AsyncSessionLocal() as db:
            wallet = await db.get(Wallet, seed["learner"].id)
            session = await db.get(ExchangeSession, session_id)
            assert wallet.balance == 100
            assert wallet.escrow_balance == 0
            assert session.payment_state == "REFUNDED"


async def test_paid_reschedule_across_week_preserves_escrow_without_using_free_quota() -> None:
    async with _seeded_integration(balance=50) as seed:
        async with AsyncSessionLocal() as db:
            session = ExchangeSession(
                match_id=seed["match"].id,
                teaching_skill_id=seed["offer"].id,
                created_by_id=seed["learner"].id,
                instructor_id=seed["instructor"].id,
                learner_id=seed["learner"].id,
                starts_at=seed["future"],
                ends_at=seed["future"] + timedelta(minutes=60),
                timezone="America/La_Paz",
                modality="VIRTUAL",
                status="ACCEPTED",
                is_free=False,
                points_required=50,
                payment_state="RESERVED",
            )
            wallet = await db.get(Wallet, seed["learner"].id)
            wallet.escrow_balance = 50
            db.add(session)
            await db.commit()
            await db.refresh(session)
            session_id = session.id

        new_start = seed["future"] + timedelta(days=7)
        app = create_application()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            result = _assert_envelope(
                await client.put(
                    f"/api/sessions/{session_id}/reschedule",
                    headers=_headers(seed["learner"]),
                    json={
                        "starts_at": new_start.isoformat(),
                        "ends_at": (new_start + timedelta(minutes=60)).isoformat(),
                    },
                ),
                200,
            )["data"]
            assert result["payment_state"] == "RESERVED"

        async with AsyncSessionLocal() as db:
            wallet = await db.get(Wallet, seed["learner"].id)
            quotas = (
                await db.execute(
                    select(WeeklySessionQuota).where(
                        WeeklySessionQuota.user_id == seed["learner"].id
                    )
                )
            ).scalars().all()
            assert wallet.balance == 50
            assert wallet.escrow_balance == 50
            assert len(quotas) == 1
            assert quotas[0].used == 2


async def test_outsider_cannot_probe_or_pay_another_members_session() -> None:
    async with _seeded_integration(balance=100) as seed:
        async with AsyncSessionLocal() as db:
            session = ExchangeSession(
                match_id=seed["match"].id,
                teaching_skill_id=seed["offer"].id,
                created_by_id=seed["learner"].id,
                instructor_id=seed["instructor"].id,
                learner_id=seed["learner"].id,
                starts_at=seed["future"],
                ends_at=seed["future"] + timedelta(minutes=60),
                timezone="America/La_Paz",
                modality="VIRTUAL",
                status="PENDING",
                is_free=False,
                points_required=50,
                payment_state="PENDING",
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)
            session_id = session.id

        app = create_application()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            _assert_envelope(
                await client.post(
                    f"/api/sessions/{session_id}/pay",
                    headers=_headers(seed["outsider"]),
                ),
                404,
            )


async def test_completion_releases_escrow_once_even_on_replay() -> None:
    async with _seeded_integration(balance=50) as seed:
        ended_at = datetime.now(UTC) - timedelta(hours=1)
        async with AsyncSessionLocal() as db:
            session = ExchangeSession(
                match_id=seed["match"].id,
                teaching_skill_id=seed["offer"].id,
                created_by_id=seed["learner"].id,
                instructor_id=seed["instructor"].id,
                learner_id=seed["learner"].id,
                starts_at=ended_at - timedelta(minutes=60),
                ends_at=ended_at,
                timezone="America/La_Paz",
                modality="VIRTUAL",
                status="ACCEPTED",
                is_free=False,
                points_required=50,
                payment_state="RESERVED",
            )
            wallet = await db.get(Wallet, seed["learner"].id)
            wallet.escrow_balance = 50
            db.add(session)
            await db.commit()
            await db.refresh(session)
            session_id = session.id

        learner_key, instructor_key = uuid4(), uuid4()
        app = create_application()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            _assert_envelope(
                await client.post(
                    f"/api/sessions/{session_id}/confirm",
                    headers=_headers(seed["learner"]),
                    json={"request_key": str(learner_key), "actual_minutes": 60, "topics": []},
                ),
                200,
            )
            completed = _assert_envelope(
                await client.post(
                    f"/api/sessions/{session_id}/confirm",
                    headers=_headers(seed["instructor"]),
                    json={
                        "request_key": str(instructor_key),
                        "actual_minutes": 60,
                        "topics": [],
                    },
                ),
                200,
            )
            assert completed["data"]["escrow_release"] == "RELEASED"
            replay = _assert_envelope(
                await client.post(
                    f"/api/sessions/{session_id}/confirm",
                    headers=_headers(seed["instructor"]),
                    json={
                        "request_key": str(instructor_key),
                        "actual_minutes": 60,
                        "topics": [],
                    },
                ),
                200,
            )
            assert replay["data"]["escrow_release"] == "RELEASED"

        async with AsyncSessionLocal() as db:
            learner_wallet = await db.get(Wallet, seed["learner"].id)
            instructor_wallet = await db.get(Wallet, seed["instructor"].id)
            transfers = await db.scalar(
                select(func.count(PointTransaction.id)).where(
                    PointTransaction.reference_id == session_id,
                    PointTransaction.user_id == seed["instructor"].id,
                )
            )
            assert learner_wallet.escrow_balance == 0
            assert instructor_wallet.balance == 50
            assert transfers == 1


async def test_noshow_is_processed_once_by_reputation_boundary() -> None:
    async with _seeded_integration() as seed:
        ended_at = datetime.now(UTC) - timedelta(hours=1)
        async with AsyncSessionLocal() as db:
            session = ExchangeSession(
                match_id=seed["match"].id,
                teaching_skill_id=seed["offer"].id,
                created_by_id=seed["learner"].id,
                instructor_id=seed["instructor"].id,
                learner_id=seed["learner"].id,
                starts_at=ended_at - timedelta(minutes=60),
                ends_at=ended_at,
                timezone="America/La_Paz",
                modality="VIRTUAL",
                status="ACCEPTED",
                is_free=True,
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)
            session_id = session.id

        request_key = uuid4()
        app = create_application()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            for _ in range(2):
                report = _assert_envelope(
                    await client.post(
                        f"/api/sessions/{session_id}/report-noshow",
                        headers=_headers(seed["instructor"]),
                        json={
                            "request_key": str(request_key),
                            "reason": "El aprendiz no se presentó ni avisó con anticipación.",
                        },
                    ),
                    200,
                )
                assert report["data"]["status"] == "PROCESSED"

            reputation = _assert_envelope(
                await client.get(f"/api/users/{seed['learner'].id}/reputation"),
                200,
            )["data"]
            assert reputation["factors"]["attendance_score"] < 100

"""HU-38 PostgreSQL/API behavior tests written before persistence exists."""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import delete, select, update

from app.core.security import create_access_token
from app.db.session import AsyncSessionLocal
from app.main import create_application
from app.models.catalog import Category, Skill
from app.models.exchange_session import BookingRestriction, ExchangeSession, SessionReminderDispatch
from app.models.match import Match
from app.models.notification import Notification
from app.models.teaching_skill import TeachingSkill
from app.models.user import User, UserRole
from app.models.user_availability import UserAvailability
from app.models.user_block import UserBlock
from app.models.user_learning_skill import UserLearningSkill


def headers(user: User) -> dict[str, str]:
    token = create_access_token(str(user.id), UserRole.MEMBER.value)
    return {"Authorization": f"Bearer {token}"}


def future_start(*, days: int = 3) -> datetime:
    """Return a stable daytime slot that never crosses the seeded 23:30 boundary."""
    return (datetime.now(UTC) + timedelta(days=days)).replace(
        hour=12, minute=0, second=0, microsecond=0
    )


def create_payload(seed: dict, *, starts_at: datetime | None = None) -> dict:
    start = starts_at or future_start()
    return {
        "match_id": str(seed["match"].id),
        "teaching_skill_id": str(seed["offer"].id),
        "instructor_id": str(seed["instructor"].id),
        "starts_at": start.isoformat(),
        "ends_at": (start + timedelta(minutes=60)).isoformat(),
        "timezone": seed["learner"].timezone,
        "modality": "VIRTUAL",
    }


def assert_envelope(response: httpx.Response, statuscode: int) -> dict:
    assert response.status_code == statuscode
    payload = response.json()
    assert payload["statuscode"] == statuscode
    assert isinstance(payload["message"], str) and payload["message"].strip()
    assert "data" in payload
    assert "error" not in payload
    return payload


@asynccontextmanager
async def seeded_exchange(*, match_status: str = "confirmed"):
    """Commit isolated seed data so concurrent requests can use separate sessions."""
    suffix = uuid4().hex
    async with AsyncSessionLocal() as db:
        category = Category(name=f"HU-38-{suffix}", slug=f"hu-38-{suffix}")
        instructor = User(
            email=f"instructor-{suffix}@example.invalid",
            full_name="Instructor HU-38",
            role=UserRole.MEMBER,
            timezone="America/La_Paz",
        )
        learner = User(
            email=f"learner-{suffix}@example.invalid",
            full_name="Learner HU-38",
            role=UserRole.MEMBER,
            timezone="America/La_Paz",
        )
        outsider = User(
            email=f"outsider-{suffix}@example.invalid",
            full_name="Outsider HU-38",
            role=UserRole.MEMBER,
            timezone="America/La_Paz",
        )
        db.add_all([category, instructor, learner, outsider])
        await db.flush()
        skill = Skill(
            name=f"Skill HU-38 {suffix}",
            slug=f"skill-hu-38-{suffix}",
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
            status=match_status,
        )
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
        }
    try:
        yield seed
    finally:
        async with AsyncSessionLocal() as cleanup:
            # Match deletion cascades sessions before the participant RESTRICT foreign keys.
            await cleanup.execute(delete(Match).where(Match.id == match.id))
            await cleanup.execute(
                delete(User).where(
                    User.id.in_(
                        [
                            instructor.id,
                            learner.id,
                            outsider.id,
                        ]
                    )
                )
            )
            await cleanup.execute(delete(Skill).where(Skill.id == skill.id))
            await cleanup.execute(delete(Category).where(Category.id == category.id))
            await cleanup.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_create_requires_auth_confirmed_match_and_membership():
    async with seeded_exchange() as seed:
        app = create_application()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            assert_envelope(await client.post("/api/sessions", json=create_payload(seed)), 401)
            assert_envelope(
                await client.post(
                    "/api/sessions",
                    headers=headers(seed["outsider"]),
                    json=create_payload(seed),
                ),
                404,
            )

    async with seeded_exchange(match_status="pending") as seed:
        app = create_application()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            assert_envelope(
                await client.post(
                    "/api/sessions",
                    headers=headers(seed["learner"]),
                    json=create_payload(seed),
                ),
                409,
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_session_options_are_private_confirmed_and_feed_create_contract():
    async with seeded_exchange() as seed:
        app = create_application()
        url = f"/api/matches/{seed['match'].id}/session-options"
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            assert_envelope(await client.get(url), 401)
            assert_envelope(await client.get(url, headers=headers(seed["outsider"])), 404)
            options = assert_envelope(
                await client.get(url, headers=headers(seed["learner"])),
                200,
            )["data"]
            assert options["match_id"] == str(seed["match"].id)
            assert options["horizon_days"] == 14
            assert options["timezone"] == seed["learner"].timezone
            assert len(options["directions"]) == 1
            direction = options["directions"][0]
            assert direction["instructor_id"] == str(seed["instructor"].id)
            assert direction["learner_id"] == str(seed["learner"].id)
            assert direction["teaching_skill_id"] == str(seed["offer"].id)
            assert direction["skill_name"] == seed["skill"].name
            slot = next(
                item
                for item in direction["common_slots"]
                if item["duration_minutes"] == 60 and item["modality"] == "VIRTUAL"
            )
            created = assert_envelope(
                await client.post(
                    "/api/sessions",
                    headers=headers(seed["learner"]),
                    json={
                        "match_id": options["match_id"],
                        "teaching_skill_id": direction["teaching_skill_id"],
                        "instructor_id": direction["instructor_id"],
                        "starts_at": slot["starts_at"],
                        "ends_at": slot["ends_at"],
                        "timezone": slot["timezone"],
                        "modality": slot["modality"],
                    },
                ),
                201,
            )
            assert created["data"]["status"] == "PENDING"

    async with seeded_exchange(match_status="pending") as seed:
        app = create_application()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            assert_envelope(
                await client.get(
                    f"/api/matches/{seed['match'].id}/session-options",
                    headers=headers(seed["learner"]),
                ),
                409,
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_create_and_list_are_private_and_report_weekly_quota():
    async with seeded_exchange() as seed:
        app = create_application()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            created = assert_envelope(
                await client.post(
                    "/api/sessions",
                    headers=headers(seed["learner"]),
                    json=create_payload(seed),
                ),
                201,
            )
            assert created["data"]["status"] == "PENDING"
            assert created["data"]["learner_id"] == str(seed["learner"].id)
            listed = assert_envelope(
                await client.get("/api/sessions", headers=headers(seed["learner"])),
                200,
            )
            assert listed["count"] == 1
            assert listed["data"]["items"][0]["id"] == created["data"]["id"]
            assert listed["data"]["free_sessions_left"] == 1
            assert listed["data"]["free_sessions_limit"] == 2
            outsider = assert_envelope(
                await client.get("/api/sessions", headers=headers(seed["outsider"])),
                200,
            )
            assert outsider["count"] == 0
            assert outsider["data"]["items"] == []


@pytest.mark.asyncio(loop_scope="session")
async def test_third_free_session_requires_real_hu42_payment():
    async with seeded_exchange() as seed:
        app = create_application()
        starts = future_start()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            for offset in (0, 2):
                response = await client.post(
                    "/api/sessions",
                    headers=headers(seed["learner"]),
                    json=create_payload(seed, starts_at=starts + timedelta(hours=offset)),
                )
                assert_envelope(response, 201)
            rejected = assert_envelope(
                await client.post(
                    "/api/sessions",
                    headers=headers(seed["learner"]),
                    json=create_payload(seed, starts_at=starts + timedelta(hours=4)),
                ),
                409,
            )
            assert rejected["data"] is None
            assert "pago" in rejected["message"].lower()


@pytest.mark.asyncio(loop_scope="session")
async def test_overlapping_session_is_rejected_without_consuming_another_quota():
    async with seeded_exchange() as seed:
        app = create_application()
        start = future_start()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            assert_envelope(
                await client.post(
                    "/api/sessions",
                    headers=headers(seed["learner"]),
                    json=create_payload(seed, starts_at=start),
                ),
                201,
            )
            assert_envelope(
                await client.post(
                    "/api/sessions",
                    headers=headers(seed["learner"]),
                    json=create_payload(seed, starts_at=start + timedelta(minutes=30)),
                ),
                409,
            )
            listed = assert_envelope(
                await client.get("/api/sessions", headers=headers(seed["learner"])),
                200,
            )
            assert listed["data"]["free_sessions_left"] == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_schedule_outside_common_availability_is_rejected():
    async with seeded_exchange() as seed:
        async with AsyncSessionLocal() as db:
            await db.execute(
                delete(UserAvailability).where(
                    UserAvailability.user_id == seed["learner"].id,
                )
            )
            await db.commit()
        app = create_application()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            assert_envelope(
                await client.post(
                    "/api/sessions",
                    headers=headers(seed["learner"]),
                    json=create_payload(seed),
                ),
                409,
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_participant_buffer_is_treated_as_occupied_time():
    async with seeded_exchange() as seed:
        async with AsyncSessionLocal() as db:
            for user_id in (seed["instructor"].id, seed["learner"].id):
                user = await db.get(User, user_id)
                user.buffer_minutes = 30
            await db.commit()
        app = create_application()
        start = future_start()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            assert_envelope(
                await client.post(
                    "/api/sessions",
                    headers=headers(seed["learner"]),
                    json=create_payload(seed, starts_at=start),
                ),
                201,
            )
            # The first meeting ends at +60; +75 starts inside its 30-minute buffer.
            assert_envelope(
                await client.post(
                    "/api/sessions",
                    headers=headers(seed["learner"]),
                    json=create_payload(seed, starts_at=start + timedelta(minutes=75)),
                ),
                409,
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_only_counterpart_accepts_and_retries_do_not_duplicate_effects():
    async with seeded_exchange() as seed:
        app = create_application()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            created = assert_envelope(
                await client.post(
                    "/api/sessions",
                    headers=headers(seed["learner"]),
                    json=create_payload(seed),
                ),
                201,
            )["data"]
            status_url = f"/api/sessions/{created['id']}/status"
            assert_envelope(
                await client.patch(
                    status_url,
                    headers=headers(seed["learner"]),
                    json={"status": "ACCEPTED"},
                ),
                409,
            )
            for _ in range(2):
                accepted = assert_envelope(
                    await client.patch(
                        status_url,
                        headers=headers(seed["instructor"]),
                        json={"status": "ACCEPTED"},
                    ),
                    200,
                )
                assert accepted["data"]["status"] == "ACCEPTED"


@pytest.mark.asyncio(loop_scope="session")
async def test_reschedule_returns_to_pending_and_moves_quota_atomically():
    async with seeded_exchange() as seed:
        app = create_application()
        first_week = future_start()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            created = assert_envelope(
                await client.post(
                    "/api/sessions",
                    headers=headers(seed["learner"]),
                    json=create_payload(seed, starts_at=first_week),
                ),
                201,
            )["data"]
            second_week = first_week + timedelta(days=7)
            rescheduled = assert_envelope(
                await client.put(
                    f"/api/sessions/{created['id']}/reschedule",
                    headers=headers(seed["instructor"]),
                    json={
                        "starts_at": second_week.isoformat(),
                        "ends_at": (second_week + timedelta(hours=1)).isoformat(),
                    },
                ),
                200,
            )["data"]
            assert rescheduled["status"] == "PENDING"
            assert rescheduled["starts_at"] == second_week.isoformat().replace("+00:00", "Z")


@pytest.mark.asyncio(loop_scope="session")
async def test_timely_cancel_restores_quota_once_and_is_terminal():
    async with seeded_exchange() as seed:
        app = create_application()
        start = future_start()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            created = assert_envelope(
                await client.post(
                    "/api/sessions",
                    headers=headers(seed["learner"]),
                    json=create_payload(seed, starts_at=start),
                ),
                201,
            )["data"]
            cancel_url = f"/api/sessions/{created['id']}/cancel"
            for _ in range(2):
                cancelled = assert_envelope(
                    await client.post(
                        cancel_url,
                        headers=headers(seed["learner"]),
                        json={"cancellation_reason": "Imprevisto familiar válido"},
                    ),
                    200,
                )["data"]
                assert cancelled["status"] == "CANCELLED"
                assert cancelled["quota_restored"] is True
            listed = assert_envelope(
                await client.get("/api/sessions", headers=headers(seed["learner"])),
                200,
            )
            assert listed["data"]["free_sessions_left"] == 2


@pytest.mark.asyncio(loop_scope="session")
async def test_late_cancel_blocks_only_booking_for_seven_days():
    async with seeded_exchange() as seed:
        app = create_application()
        # Keep the session inside the seeded 00:00-23:30 local availability.
        start = datetime.now(UTC) + timedelta(hours=20)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            created = assert_envelope(
                await client.post(
                    "/api/sessions",
                    headers=headers(seed["learner"]),
                    json=create_payload(seed, starts_at=start),
                ),
                201,
            )["data"]
            cancelled = assert_envelope(
                await client.post(
                    f"/api/sessions/{created['id']}/cancel",
                    headers=headers(seed["learner"]),
                    json={"cancellation_reason": "Cancelación tardía justificada"},
                ),
                200,
            )["data"]
            assert cancelled["quota_restored"] is False
            assert cancelled["booking_blocked_until"] is not None
            assert_envelope(
                await client.post(
                    "/api/sessions",
                    headers=headers(seed["learner"]),
                    json=create_payload(
                        seed,
                        starts_at=future_start(),
                    ),
                ),
                409,
            )
            # Booking restriction never blocks private reads or authentication.
            assert_envelope(
                await client.get("/api/sessions", headers=headers(seed["learner"])),
                200,
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_hu26_bilateral_block_prevents_new_booking():
    async with seeded_exchange() as seed:
        async with AsyncSessionLocal() as db:
            db.add(
                UserBlock(
                    blocker_id=seed["instructor"].id,
                    blocked_id=seed["learner"].id,
                )
            )
            await db.commit()
        app = create_application()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            assert_envelope(
                await client.post(
                    "/api/sessions",
                    headers=headers(seed["learner"]),
                    json=create_payload(seed),
                ),
                409,
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_concurrent_requests_cannot_reserve_the_same_last_free_quota():
    async with seeded_exchange() as seed:
        app = create_application()
        base = future_start()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            assert_envelope(
                await client.post(
                    "/api/sessions",
                    headers=headers(seed["learner"]),
                    json=create_payload(seed, starts_at=base),
                ),
                201,
            )
            responses = await asyncio.gather(
                client.post(
                    "/api/sessions",
                    headers=headers(seed["learner"]),
                    json=create_payload(seed, starts_at=base + timedelta(hours=2)),
                ),
                client.post(
                    "/api/sessions",
                    headers=headers(seed["learner"]),
                    json=create_payload(seed, starts_at=base + timedelta(hours=4)),
                ),
            )
            assert sorted(response.status_code for response in responses) == [201, 409]


@pytest.mark.asyncio(loop_scope="session")
async def test_fourth_monthly_cancellation_blocks_booking_but_not_reading():
    async with seeded_exchange() as seed:
        app = create_application()
        base = future_start(days=5)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            for offset in range(4):
                created = assert_envelope(
                    await client.post(
                        "/api/sessions",
                        headers=headers(seed["learner"]),
                        json=create_payload(seed, starts_at=base + timedelta(hours=offset * 2)),
                    ),
                    201,
                )["data"]
                cancelled = assert_envelope(
                    await client.post(
                        f"/api/sessions/{created['id']}/cancel",
                        headers=headers(seed["learner"]),
                        json={"cancellation_reason": "Cambio de agenda informado a tiempo"},
                    ),
                    200,
                )["data"]
            assert cancelled["booking_blocked_until"] is not None
            assert_envelope(
                await client.post(
                    "/api/sessions",
                    headers=headers(seed["learner"]),
                    json=create_payload(seed, starts_at=base + timedelta(days=1)),
                ),
                409,
            )
            assert_envelope(
                await client.get("/api/sessions", headers=headers(seed["learner"])),
                200,
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_expired_booking_restriction_does_not_block_a_new_session():
    async with seeded_exchange() as seed:
        app = create_application()
        start = datetime.now(UTC) + timedelta(hours=20)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            created = assert_envelope(
                await client.post(
                    "/api/sessions",
                    headers=headers(seed["learner"]),
                    json=create_payload(seed, starts_at=start),
                ),
                201,
            )["data"]
            assert_envelope(
                await client.post(
                    f"/api/sessions/{created['id']}/cancel",
                    headers=headers(seed["learner"]),
                    json={"cancellation_reason": "Cancelación tardía por emergencia"},
                ),
                200,
            )
            async with AsyncSessionLocal() as db:
                await db.execute(
                    update(BookingRestriction)
                    .where(BookingRestriction.user_id == seed["learner"].id)
                    .values(
                        starts_at=datetime.now(UTC) - timedelta(days=2),
                        ends_at=datetime.now(UTC) - timedelta(days=1),
                    )
                )
                await db.commit()
            assert_envelope(
                await client.post(
                    "/api/sessions",
                    headers=headers(seed["learner"]),
                    json=create_payload(seed, starts_at=future_start()),
                ),
                201,
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_session_lifecycle_emits_durable_notifications_without_retry_duplicates():
    async with seeded_exchange() as seed:
        app = create_application()
        start = future_start()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            created = assert_envelope(
                await client.post(
                    "/api/sessions",
                    headers=headers(seed["learner"]),
                    json=create_payload(seed, starts_at=start),
                ),
                201,
            )["data"]
            status_url = f"/api/sessions/{created['id']}/status"
            for _ in range(2):
                assert_envelope(
                    await client.patch(
                        status_url,
                        headers=headers(seed["instructor"]),
                        json={"status": "ACCEPTED"},
                    ),
                    200,
                )
            new_start = start + timedelta(days=7)
            assert_envelope(
                await client.put(
                    f"/api/sessions/{created['id']}/reschedule",
                    headers=headers(seed["instructor"]),
                    json={
                        "starts_at": new_start.isoformat(),
                        "ends_at": (new_start + timedelta(hours=1)).isoformat(),
                    },
                ),
                200,
            )
            cancel_url = f"/api/sessions/{created['id']}/cancel"
            for _ in range(2):
                assert_envelope(
                    await client.post(
                        cancel_url,
                        headers=headers(seed["learner"]),
                        json={"cancellation_reason": "Cambio de agenda informado a tiempo"},
                    ),
                    200,
                )
        async with AsyncSessionLocal() as db:
            types = list(
                (
                    await db.scalars(
                        select(Notification.type).where(
                            Notification.user_id.in_(
                                [
                                    seed["instructor"].id,
                                    seed["learner"].id,
                                ]
                            )
                        )
                    )
                ).all()
            )
        assert sorted(types) == sorted(
            [
                "SESSION_PROPOSED",
                "SESSION_ACCEPTED",
                "SESSION_RESCHEDULED",
                "SESSION_CANCELLED",
            ]
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_due_reminders_are_persisted_once_and_reschedule_gets_new_identities():
    from app.services.session_reminder_service import dispatch_due_reminders

    async with seeded_exchange() as seed:
        app = create_application()
        starts_at = future_start()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            created = assert_envelope(
                await client.post(
                    "/api/sessions",
                    headers=headers(seed["learner"]),
                    json=create_payload(seed, starts_at=starts_at),
                ),
                201,
            )["data"]
            assert_envelope(
                await client.patch(
                    f"/api/sessions/{created['id']}/status",
                    headers=headers(seed["instructor"]),
                    json={"status": "ACCEPTED"},
                ),
                200,
            )

        reminder_now = starts_at - timedelta(hours=24)
        async with AsyncSessionLocal() as db:
            first = await dispatch_due_reminders(db, now=reminder_now)
            await db.commit()
        async with AsyncSessionLocal() as db:
            retry = await dispatch_due_reminders(db, now=reminder_now)
            await db.commit()
            first_dispatches = list(
                (
                    await db.scalars(
                        select(SessionReminderDispatch).where(
                            SessionReminderDispatch.session_id == UUID(created["id"])
                        )
                    )
                ).all()
            )
        assert len(first) == 2
        assert retry == []
        assert len(first_dispatches) == 2
        assert {item.user_id for item in first_dispatches} == {
            seed["instructor"].id,
            seed["learner"].id,
        }
        assert all(item.notification_id is not None for item in first_dispatches)

        moved_start = starts_at + timedelta(days=1)
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(ExchangeSession)
                .where(ExchangeSession.id == UUID(created["id"]))
                .values(
                    starts_at=moved_start,
                    ends_at=moved_start + timedelta(hours=1),
                    status="ACCEPTED",
                )
            )
            await db.commit()
        async with AsyncSessionLocal() as db:
            moved = await dispatch_due_reminders(db, now=moved_start - timedelta(hours=24))
            await db.commit()
            all_dispatches = list(
                (
                    await db.scalars(
                        select(SessionReminderDispatch).where(
                            SessionReminderDispatch.session_id == UUID(created["id"])
                        )
                    )
                ).all()
            )
        assert len(moved) == 2
        assert len(all_dispatches) == 4
        assert len({item.event_id for item in all_dispatches}) == 4

        async with AsyncSessionLocal() as db:
            await db.execute(
                update(ExchangeSession)
                .where(ExchangeSession.id == UUID(created["id"]))
                .values(status="CANCELLED")
            )
            await db.commit()
        async with AsyncSessionLocal() as db:
            terminal = await dispatch_due_reminders(db, now=moved_start - timedelta(hours=1))
            await db.commit()
        assert terminal == []


def test_session_reminder_task_is_registered_every_five_minutes():
    from app.core.celery_app import celery_app
    from app.tasks.session_reminders import dispatch_session_reminders

    assert dispatch_session_reminders.name == "sessions.dispatch_due_reminders"
    schedule = celery_app.conf.beat_schedule["session-reminders-every-five-minutes"]
    assert schedule["task"] == dispatch_session_reminders.name
    assert schedule["schedule"] == 300.0


@pytest.mark.asyncio(loop_scope="session")
async def test_email_reminder_delivery_is_persisted_and_not_repeated():
    from app.models.exchange_session import SessionReminderEmailDelivery
    from app.models.notification_preference import NotificationPreference
    from app.services.session_reminder_email_delivery_service import (
        deliver_pending_reminder_emails,
    )
    from app.services.session_reminder_service import dispatch_due_reminders

    class RecordingSender:
        def __init__(self) -> None:
            self.messages = []

        async def send(self, content) -> None:
            self.messages.append(content)

    async with seeded_exchange() as seed:
        starts_at = future_start()
        app = create_application()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            created = assert_envelope(
                await client.post(
                    "/api/sessions",
                    headers=headers(seed["learner"]),
                    json=create_payload(seed, starts_at=starts_at),
                ),
                201,
            )["data"]
            assert_envelope(
                await client.patch(
                    f"/api/sessions/{created['id']}/status",
                    headers=headers(seed["instructor"]),
                    json={"status": "ACCEPTED"},
                ),
                200,
            )
        async with AsyncSessionLocal() as db:
            db.add_all(
                [
                    NotificationPreference(user_id=user.id, email=True)
                    for user in (seed["instructor"], seed["learner"])
                ]
            )
            await db.commit()

        reminder_now = starts_at - timedelta(hours=24)
        async with AsyncSessionLocal() as db:
            await dispatch_due_reminders(db, now=reminder_now)
            await db.commit()
            deliveries = list(
                (
                    await db.scalars(
                        select(SessionReminderEmailDelivery).where(
                            SessionReminderEmailDelivery.session_id == UUID(created["id"])
                        )
                    )
                ).all()
            )
        assert len(deliveries) == 2
        assert {item.status for item in deliveries} == {"PENDING"}

        sender = RecordingSender()
        async with AsyncSessionLocal() as db:
            first = await deliver_pending_reminder_emails(
                db,
                sender=sender,
                now=reminder_now,
                sessions_url="http://localhost:5173/app/sessions",
            )
            await db.commit()
        async with AsyncSessionLocal() as db:
            retry = await deliver_pending_reminder_emails(
                db,
                sender=sender,
                now=reminder_now,
                sessions_url="http://localhost:5173/app/sessions",
            )
            await db.commit()
            stored = list(
                (
                    await db.scalars(
                        select(SessionReminderEmailDelivery).where(
                            SessionReminderEmailDelivery.session_id == UUID(created["id"])
                        )
                    )
                ).all()
            )
        assert first.sent == 2
        assert retry.sent == 0
        assert len(sender.messages) == 2
        assert len({message.message_id for message in sender.messages}) == 2
        assert {item.status for item in stored} == {"SENT"}
        assert {item.attempt_count for item in stored} == {1}


@pytest.mark.asyncio(loop_scope="session")
async def test_email_delivery_skips_a_cancelled_session_before_smtp_send():
    from app.models.exchange_session import SessionReminderEmailDelivery
    from app.models.notification_preference import NotificationPreference
    from app.services.session_reminder_email_delivery_service import (
        deliver_pending_reminder_emails,
    )
    from app.services.session_reminder_service import dispatch_due_reminders

    class RejectUnexpectedSend:
        async def send(self, content) -> None:
            raise AssertionError(f"No debió enviarse {content.message_id}")

    async with seeded_exchange() as seed:
        starts_at = future_start()
        app = create_application()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            created = assert_envelope(
                await client.post(
                    "/api/sessions",
                    headers=headers(seed["learner"]),
                    json=create_payload(seed, starts_at=starts_at),
                ),
                201,
            )["data"]
            assert_envelope(
                await client.patch(
                    f"/api/sessions/{created['id']}/status",
                    headers=headers(seed["instructor"]),
                    json={"status": "ACCEPTED"},
                ),
                200,
            )
        reminder_now = starts_at - timedelta(hours=24)
        async with AsyncSessionLocal() as db:
            db.add(NotificationPreference(user_id=seed["learner"].id, email=True))
            await dispatch_due_reminders(db, now=reminder_now)
            await db.execute(
                update(ExchangeSession)
                .where(ExchangeSession.id == UUID(created["id"]))
                .values(status="CANCELLED")
            )
            await db.commit()
        async with AsyncSessionLocal() as db:
            result = await deliver_pending_reminder_emails(
                db,
                sender=RejectUnexpectedSend(),
                now=reminder_now,
                sessions_url="http://localhost:5173/app/sessions",
            )
            await db.commit()
            statuses = list(
                (
                    await db.scalars(
                        select(SessionReminderEmailDelivery.status).where(
                            SessionReminderEmailDelivery.session_id == UUID(created["id"])
                        )
                    )
                ).all()
            )
        assert result.skipped == 1
        assert statuses == ["SKIPPED"]

from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_engine
from app.models.catalog import Category, Skill
from app.models.exchange_session import (
    BookingRestriction,
    ExchangeSession,
    SessionAuditEvent,
    SessionCancellation,
    SessionQuotaMovement,
    WeeklySessionQuota,
)
from app.models.match import Match
from app.models.teaching_skill import TeachingSkill
from app.models.user import User, UserRole

EXPECTED_TABLES = {
    "exchange_sessions",
    "weekly_session_quotas",
    "session_quota_movements",
    "session_cancellations",
    "booking_restrictions",
    "session_audit_events",
}


def test_hu38_models_are_registered_with_canonical_tables():
    tables = {
        model.__table__.name
        for model in (
            ExchangeSession,
            WeeklySessionQuota,
            SessionQuotaMovement,
            SessionCancellation,
            BookingRestriction,
            SessionAuditEvent,
        )
    }
    assert tables == EXPECTED_TABLES


def test_model_metadata_contains_required_constraints_and_foreign_keys():
    session = ExchangeSession.__table__
    constraint_names = {constraint.name for constraint in session.constraints}
    assert {
        "ck_exchange_sessions_distinct_members",
        "ck_exchange_sessions_duration",
        "ck_exchange_sessions_modality",
        "ck_exchange_sessions_status",
        "ck_exchange_sessions_points_required",
        "ck_exchange_sessions_payment_state",
        "ck_exchange_sessions_cancellation_reason",
    } <= constraint_names
    targets = {
        foreign_key.target_fullname
        for column in session.columns
        for foreign_key in column.foreign_keys
    }
    assert {
        "matches.id",
        "user_teaching_skills.id",
        "users.id",
    } <= targets

    quota_constraints = {
        constraint.name for constraint in WeeklySessionQuota.__table__.constraints
    }
    assert "uq_weekly_session_quota_user_week" in quota_constraints
    assert "ck_weekly_session_quotas_used" in quota_constraints
    cancellation_constraints = {
        constraint.name for constraint in SessionCancellation.__table__.constraints
    }
    assert "uq_session_cancellations_session" in cancellation_constraints


@pytest.mark.asyncio(loop_scope="session")
async def test_migrated_database_has_hu38_tables_indexes_and_constraints():
    async with async_engine.connect() as connection:
        def inspect_schema(sync_connection):
            inspector = inspect(sync_connection)
            tables = set(inspector.get_table_names())
            session_indexes = {
                item["name"] for item in inspector.get_indexes("exchange_sessions")
            }
            quota_unique = {
                item["name"] for item in inspector.get_unique_constraints("weekly_session_quotas")
            }
            return tables, session_indexes, quota_unique

        tables, session_indexes, quota_unique = await connection.run_sync(inspect_schema)
    assert EXPECTED_TABLES <= tables
    assert {
        "ix_exchange_sessions_instructor_starts",
        "ix_exchange_sessions_learner_starts",
        "ix_exchange_sessions_match_status",
    } <= session_indexes
    assert "uq_weekly_session_quota_user_week" in quota_unique


@pytest.mark.asyncio(loop_scope="session")
async def test_postgresql_enforces_duration_quota_and_single_cancellation():
    suffix = uuid4().hex
    async with async_engine.connect() as connection:
        transaction = await connection.begin()
        try:
            async with AsyncSession(bind=connection, expire_on_commit=False) as db:
                category = Category(name=f"HU38 persistence {suffix}", slug=f"hu38-{suffix}")
                instructor = User(
                    email=f"instructor-{suffix}@example.invalid",
                    full_name="Instructor",
                    role=UserRole.MEMBER,
                )
                learner = User(
                    email=f"learner-{suffix}@example.invalid",
                    full_name="Learner",
                    role=UserRole.MEMBER,
                )
                db.add_all([category, instructor, learner])
                await db.flush()
                skill = Skill(
                    name=f"HU38 Skill {suffix}",
                    slug=f"hu38-skill-{suffix}",
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
                first, second = sorted([instructor.id, learner.id])
                match = Match(member_a_id=first, member_b_id=second, status="confirmed")
                db.add_all([offer, match])
                await db.flush()

                starts_at = datetime.now(UTC) + timedelta(days=3)
                session = ExchangeSession(
                    match_id=match.id,
                    teaching_skill_id=offer.id,
                    created_by_id=learner.id,
                    instructor_id=instructor.id,
                    learner_id=learner.id,
                    starts_at=starts_at,
                    ends_at=starts_at + timedelta(hours=1),
                    timezone="America/La_Paz",
                    modality="VIRTUAL",
                    status="PENDING",
                    is_free=True,
                )
                quota = WeeklySessionQuota(
                    user_id=learner.id,
                    week_start=date(2026, 11, 16),
                    used=1,
                    version=1,
                )
                db.add_all([session, quota])
                await db.flush()

                with pytest.raises(IntegrityError):
                    async with db.begin_nested():
                        db.add(WeeklySessionQuota(
                            user_id=learner.id,
                            week_start=date(2026, 11, 23),
                            used=3,
                            version=1,
                        ))
                        await db.flush()

                with pytest.raises(IntegrityError):
                    async with db.begin_nested():
                        db.add(ExchangeSession(
                            match_id=match.id,
                            teaching_skill_id=offer.id,
                            created_by_id=learner.id,
                            instructor_id=instructor.id,
                            learner_id=learner.id,
                            starts_at=starts_at + timedelta(days=1),
                            ends_at=starts_at + timedelta(days=1, minutes=61),
                            timezone="America/La_Paz",
                            modality="VIRTUAL",
                            status="PENDING",
                            is_free=True,
                        ))
                        await db.flush()

                first_cancel = SessionCancellation(
                    session_id=session.id,
                    cancelled_by_id=learner.id,
                    reason="Imprevisto familiar válido",
                    cancelled_at=datetime.now(UTC),
                    is_timely=True,
                    quota_restored=True,
                    triggers_booking_block=False,
                )
                db.add(first_cancel)
                await db.flush()
                with pytest.raises(IntegrityError):
                    async with db.begin_nested():
                        db.add(SessionCancellation(
                            session_id=session.id,
                            cancelled_by_id=instructor.id,
                            reason="Segundo intento no permitido",
                            cancelled_at=datetime.now(UTC),
                            is_timely=True,
                            quota_restored=False,
                            triggers_booking_block=False,
                        ))
                        await db.flush()
        finally:
            await transaction.rollback()

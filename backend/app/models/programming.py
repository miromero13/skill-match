import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Challenge(Base, TimestampMixin):
    """Versioned evaluation challenge; SANDBOX is the first supported modality."""

    __tablename__ = "challenges"
    __table_args__ = (
        UniqueConstraint("skill_id", "level_number", "version", name="uq_challenge_version"),
        CheckConstraint("level_number BETWEEN 1 AND 5", name="ck_challenge_level"),
        CheckConstraint("evaluation_modality IN ('SANDBOX', 'SPREADSHEET')", name="ck_challenge_modality"),
        CheckConstraint("execution_profile <> ''", name="ck_challenge_profile"),
        CheckConstraint("status IN ('DRAFT', 'PUBLISHED', 'ARCHIVED')", name="ck_challenge_status"),
        CheckConstraint("time_limit_ms BETWEEN 100 AND 30000", name="ck_challenge_time_limit"),
        CheckConstraint("memory_limit_mb BETWEEN 16 AND 1024", name="ck_challenge_memory_limit"),
        CheckConstraint("max_output_bytes BETWEEN 1024 AND 1048576", name="ck_challenge_output_limit"),
        Index("ix_challenges_published", "skill_id", "level_number", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skills.id", ondelete="RESTRICT"), nullable=False, index=True)
    challenge_type_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("challenge_types.id", ondelete="SET NULL"), nullable=True, index=True)
    level_number: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    evaluation_modality: Mapped[str] = mapped_column(String(24), default="SANDBOX", nullable=False)
    execution_profile: Mapped[str] = mapped_column(String(40), default="PYTHON_3_12", nullable=False)
    starter_code: Mapped[str] = mapped_column(Text, default="", nullable=False)
    time_limit_ms: Mapped[int] = mapped_column(Integer, default=2000, nullable=False)
    memory_limit_mb: Mapped[int] = mapped_column(Integer, default=128, nullable=False)
    max_output_bytes: Mapped[int] = mapped_column(Integer, default=65536, nullable=False)
    allowed_imports: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    blocked_imports: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="DRAFT", nullable=False, index=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    tests: Mapped[list["ChallengeTestCase"]] = relationship(
        back_populates="challenge", cascade="all, delete-orphan", order_by="ChallengeTestCase.order_index"
    )


class ChallengeTestCase(Base, TimestampMixin):
    __tablename__ = "challenge_test_cases"
    __table_args__ = (
        UniqueConstraint("challenge_id", "order_index", name="uq_challenge_test_order"),
        CheckConstraint("visibility IN ('PUBLIC', 'HIDDEN')", name="ck_challenge_test_visibility"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    challenge_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("challenges.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    stdin_data: Mapped[str] = mapped_column(Text, default="", nullable=False)
    expected_stdout: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(String(8), default="HIDDEN", nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    challenge: Mapped[Challenge] = relationship(back_populates="tests")


class ChallengeSubmission(Base, TimestampMixin):
    __tablename__ = "challenge_submissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False, index=True)
    challenge_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("challenges.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    passed_tests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tests: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    result: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    defense_submission_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    defense_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    defense_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    defense_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)

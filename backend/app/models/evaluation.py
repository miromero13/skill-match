"""Shared evaluation envelope; preparation does not consume an attempt."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Evaluation(Base, TimestampMixin):
    __tablename__ = "evaluations"
    __table_args__ = (UniqueConstraint("user_id", "skill_id", name="uq_evaluation_free_skill"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skills.id", ondelete="RESTRICT"))
    teaching_skill_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("user_teaching_skills.id", ondelete="SET NULL"), nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), default="PENDING_CALIBRATION")
    biometric_consent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    policy_version: Mapped[str] = mapped_column(String(20))
    ip_address: Mapped[str] = mapped_column(String(64))
    user_agent: Mapped[str] = mapped_column(String(512))
    # Only the future calibrated exam-start transition may set this timestamp.
    # Counting starts, not status, prevents abandonment from refunding attempts.
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    final_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)

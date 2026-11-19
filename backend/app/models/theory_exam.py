"""Theory sessions fix question revisions and timing at the real attempt start."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Float, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TheoryExam(Base):
    __tablename__ = "theory_exams"
    evaluation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("evaluations.id", ondelete="RESTRICT"), primary_key=True)
    level_number: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    questions: Mapped[list[dict]] = mapped_column(JSONB)
    current_position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    question_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    answers: Mapped[list[dict]] = mapped_column(JSONB, default=list, server_default="[]")
    text_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    grading_provider: Mapped[str | None] = mapped_column(String(16), nullable=True)
    grading_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    grading_prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    grading_state: Mapped[str] = mapped_column(String(16), default="PENDING", server_default="PENDING")
    grading_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    grading_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    grading_error: Mapped[str | None] = mapped_column(String(64), nullable=True)

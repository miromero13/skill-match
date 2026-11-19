"""Immutable question revisions; version one is the stable editing lock."""
import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class TheoryQuestion(Base, TimestampMixin):
    __tablename__ = "theory_question_revisions"
    __table_args__ = (
        CheckConstraint("version >= 1", name="ck_theory_question_version"),
        CheckConstraint("level_number BETWEEN 1 AND 5", name="ck_theory_question_level"),
        CheckConstraint("status IN ('DRAFT', 'PUBLISHED', 'ARCHIVED')", name="ck_theory_question_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    skill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("skills.id", ondelete="RESTRICT"), index=True)
    level_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="DRAFT")
    content: Mapped[dict] = mapped_column(JSONB)

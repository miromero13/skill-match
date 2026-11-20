import uuid
from enum import Enum

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class EvidenceType(str, Enum):
    REPOSITORY = "REPOSITORY"
    VIDEO = "VIDEO"
    CERTIFICATE = "CERTIFICATE"
    OTHER = "OTHER"


class SkillEvidence(Base, TimestampMixin):
    """Enlace complementario de una oferta; no concede certificación."""

    __tablename__ = "skill_evidences"
    __table_args__ = (
        UniqueConstraint("teaching_skill_id", "url", name="uq_skill_evidences_skill_url"),
        CheckConstraint(
            "evidence_type IN ('REPOSITORY', 'VIDEO', 'CERTIFICATE', 'OTHER')",
            name="ck_skill_evidences_type",
        ),
        CheckConstraint("length(btrim(title)) > 0", name="ck_skill_evidences_title"),
        CheckConstraint(
            "url LIKE 'http://%' OR url LIKE 'https://%'",
            name="ck_skill_evidences_url_scheme",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teaching_skill_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "user_teaching_skills.id", ondelete="CASCADE",
            name="fk_skill_evidences_teaching_skill_id",
        ),
        nullable=False, index=True,
    )
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(20), nullable=False)

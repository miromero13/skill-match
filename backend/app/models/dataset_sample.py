import uuid
from typing import Any, Optional
from sqlalchemy import JSON, Boolean, CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class DatasetSample(Base, TimestampMixin):
    __tablename__ = "dataset_samples"
    __table_args__ = (
        CheckConstraint(
            "file_format IN ('mp4', 'wav', 'py', 'webm', 'mov')",
            name="ck_dataset_samples_format",
        ),
        CheckConstraint(
            "signed_consent IS TRUE",
            name="ck_dataset_samples_signed_consent",
        ),
        CheckConstraint(
            "length(file_hash_sha256) = 64",
            name="ck_dataset_samples_hash_length",
        ),
        CheckConstraint(
            "sample_role IN ('TRAINING', 'REFERENCE')",
            name="ck_dataset_samples_sample_role",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    discipline: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    challenge: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    hardware_info: Mapped[str] = mapped_column(String(255), nullable=False)
    signed_consent: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    file_format: Mapped[str] = mapped_column(String(10), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    file_hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    uploaded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    participant_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True
    )
    level_label: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    manual_touch_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    noise_level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    surface: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    split: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    # Skill lab linkage (catalog skill / level / rubric criterion); null for legacy samples.
    skill_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skills.id", ondelete="SET NULL", name="fk_dataset_samples_skill_id"),
        nullable=True,
        index=True,
    )
    skill_level_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skill_levels.id", ondelete="SET NULL", name="fk_dataset_samples_skill_level_id"),
        nullable=True,
        index=True,
    )
    criterion_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    sample_role: Mapped[str] = mapped_column(
        String(20), default="TRAINING", server_default="TRAINING", nullable=False
    )
    analysis: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    uploaded_by: Mapped[Optional["User"]] = relationship(  # noqa: F821
        "User", backref="dataset_samples"
    )

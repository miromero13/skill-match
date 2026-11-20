from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class ValidationSessionState(str, enum.Enum):
    CREATED = "created"
    ENV_CHECK = "env_check"
    LIVENESS = "liveness"
    CALIBRATION = "calibration"
    RECORDING = "recording"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    SCORED = "scored"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class ChallengeSegmentType(str, enum.Enum):
    LOW = "LOW"
    HIGH = "HIGH"
    SLOW = "SLOW"
    FAST = "FAST"


class DetectedEventType(str, enum.Enum):
    TOUCH_VIDEO = "touch_video"
    IMPACT_AUDIO = "impact_audio"
    TOUCH_FUSED = "touch_fused"


class DetectedEventStatus(str, enum.Enum):
    CONFIRMED = "confirmed"
    VIDEO_ONLY = "video_only"
    AUDIO_ONLY = "audio_only"


class ValidationSession(Base, TimestampMixin):
    __tablename__ = "validation_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    skill_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skills.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    estado: Mapped[str] = mapped_column(
        String(30),
        default=ValidationSessionState.CREATED.value,
        nullable=False,
        index=True,
    )
    semilla: Mapped[int] = mapped_column(Integer, nullable=False)
    plan_firmado: Mapped[str] = mapped_column(Text, nullable=False)
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    finalizada_en: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    version_modelo: Mapped[str] = mapped_column(
        String(64), default="rules-v1", nullable=False
    )
    version_config: Mapped[str] = mapped_column(String(64), nullable=False)

    segments: Mapped[list[ChallengeSegment]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChallengeSegment.indice",
    )
    evidence_files: Mapped[list[EvidenceFile]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    detected_events: Mapped[list[DetectedEvent]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="DetectedEvent.t_ms",
    )
    features: Mapped[SessionFeature | None] = relationship(
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
    )
    result: Mapped[ValidationResult | None] = relationship(
        back_populates="session",
        uselist=False,
        cascade="all, delete-orphan",
    )
    fraud_incidents: Mapped[list[FraudIncident]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="FraudIncident.t_ms",
    )


class ChallengeSegment(Base, TimestampMixin):
    __tablename__ = "challenge_segments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("validation_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    indice: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    inicio_servidor_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duracion_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    cumplimiento: Mapped[float | None] = mapped_column(Float, nullable=True)
    latencia_reaccion_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    session: Mapped[ValidationSession] = relationship(back_populates="segments")


class EvidenceFile(Base, TimestampMixin):
    __tablename__ = "evidence_files"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("validation_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    ruta_minio: Mapped[str] = mapped_column(String(500), nullable=False)
    duracion_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    expira_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    session: Mapped[ValidationSession] = relationship(back_populates="evidence_files")


class DetectedEvent(Base, TimestampMixin):
    __tablename__ = "detected_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("validation_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    t_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    estado: Mapped[str] = mapped_column(String(30), nullable=False)
    confianza: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    session: Mapped[ValidationSession] = relationship(back_populates="detected_events")


class SessionFeature(Base, TimestampMixin):
    __tablename__ = "session_features"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("validation_sessions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    features_json: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )

    session: Mapped[ValidationSession] = relationship(back_populates="features")


class ValidationResult(Base, TimestampMixin):
    __tablename__ = "validation_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("validation_sessions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    nivel: Mapped[str] = mapped_column(String(40), nullable=False)
    probabilidades: Mapped[dict[str, float]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    confianza: Mapped[float] = mapped_column(Float, nullable=False)
    puntaje_riesgo: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    puntaje_1_100: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    puntaje_calibrado: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    requiere_revision: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    retroalimentacion: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )

    session: Mapped[ValidationSession] = relationship(back_populates="result")


class FraudIncident(Base, TimestampMixin):
    __tablename__ = "fraud_incidents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("validation_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tipo: Mapped[str] = mapped_column(String(60), nullable=False)
    severidad: Mapped[str] = mapped_column(String(20), nullable=False)
    t_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    detalle: Mapped[str | None] = mapped_column(Text, nullable=True)

    session: Mapped[ValidationSession] = relationship(back_populates="fraud_incidents")


class ModelVersion(Base, TimestampMixin):
    __tablename__ = "model_versions"
    __table_args__ = (
        # One active per-skill validator; global rows (skill_id NULL) are unaffected.
        Index(
            "uq_model_versions_active_skill",
            "skill_id",
            unique=True,
            postgresql_where=text("activa IS TRUE AND skill_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    ruta_onnx: Mapped[str] = mapped_column(String(500), nullable=False)
    metricas: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    activa: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Per-skill lab validator (`nombre='skill_validator'`); null for football/flute global models.
    skill_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("skills.id", ondelete="CASCADE", name="fk_model_versions_skill_id"),
        nullable=True,
        index=True,
    )

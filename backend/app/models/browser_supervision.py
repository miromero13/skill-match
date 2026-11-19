"""Trial-only browser telemetry: deliberately no relationship to evaluations."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BrowserTrial(Base):
    __tablename__ = "browser_supervision_trials"
    __table_args__ = (Index("uq_browser_trial_open_user", "user_id", unique=True,
                            postgresql_where=text("closed_at IS NULL")),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tab_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    event_count: Mapped[int] = mapped_column(Integer, default=0)
    # Server receipt time of the latest audiovisual window; basis of WINDOW_GAP detection.
    last_av_window_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BrowserIncident(Base):
    __tablename__ = "browser_supervision_incidents"
    __table_args__ = (UniqueConstraint("trial_id", "sequence", name="uq_browser_incident_sequence"),
                     Index("ix_browser_incident_received", "trial_id", "received_at"))
    trial_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("browser_supervision_trials.id", ondelete="CASCADE"), primary_key=True)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    sequence: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(32))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)

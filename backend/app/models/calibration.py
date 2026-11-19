"""Short-lived, single-use preparation challenges, never exam attempts."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class CalibrationChallenge(Base, TimestampMixin):
    __tablename__ = "evaluation_calibration_challenges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evaluations.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(20))
    enrollment_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checks: Mapped[dict[str, bool] | None] = mapped_column(JSON, nullable=True)
    # What a passed calibration gives supervision (T9): the screen zone, the voiceprint (a biometric, with the ambient
    # noise floor) and the occlusion reference. They stay on the server: no response ever carries them.
    gaze_zone: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    voiceprint: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    occlusion_ref: Mapped[dict | None] = mapped_column(JSON, nullable=True)

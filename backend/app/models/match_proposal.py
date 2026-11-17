from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class MatchProposal(Base, TimestampMixin):
    __tablename__ = "match_proposals"
    __table_args__ = (
        UniqueConstraint("match_id", "version", name="uq_match_proposal_version"),
        CheckConstraint("version > 0", name="ck_match_proposal_version"),
        CheckConstraint(
            "status IN ('pending', 'superseded', 'accepted', 'declined')",
            name="ck_match_proposal_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    match_id: Mapped[UUID] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"))
    proposed_by_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True,
    )
    version: Mapped[int]
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), server_default="pending")


class MatchDismissal(Base, TimestampMixin):
    __tablename__ = "match_dismissals"

    match_id: Mapped[UUID] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), primary_key=True,
    )
    member_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True,
    )


class MatchMessage(Base, TimestampMixin):
    __tablename__ = "match_messages"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    match_id: Mapped[UUID] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), index=True,
    )
    sender_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True,
    )
    body: Mapped[str] = mapped_column(String(2000))

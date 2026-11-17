from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Match(Base, TimestampMixin):
    __tablename__ = "matches"

    __table_args__ = (
        CheckConstraint(
            "member_a_id < member_b_id",
            name="ck_matches_members_order",
        ),
        UniqueConstraint(
            "member_a_id", "member_b_id", name="uq_matches_members",
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    member_a_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    member_b_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending",
    )
"""Expand durable notification types for HU-38 session lifecycle.

Revision ID: e38c4a6b7d82
Revises: d38b2f3a5c71
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e38c4a6b7d82"
down_revision: str | None = "d38b2f3a5c71"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_notifications_type", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_type",
        "notifications",
        "type IN ('MATCH_RECEIVED', 'MATCH_CONFIRMED', 'SESSION_PROPOSED', "
        "'SESSION_ACCEPTED', 'SESSION_REJECTED', 'SESSION_RESCHEDULED', "
        "'SESSION_CANCELLED', 'SESSION_REMINDER', 'POINTS_RECEIVED', 'OTHER')",
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM notifications WHERE type IN "
        "('SESSION_ACCEPTED', 'SESSION_REJECTED', 'SESSION_RESCHEDULED', "
        "'SESSION_CANCELLED', 'SESSION_REMINDER')"
    )
    op.drop_constraint("ck_notifications_type", "notifications", type_="check")
    op.create_check_constraint(
        "ck_notifications_type",
        "notifications",
        "type IN ('MATCH_RECEIVED', 'MATCH_CONFIRMED', 'SESSION_PROPOSED', "
        "'POINTS_RECEIVED', 'OTHER')",
    )

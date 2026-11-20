"""Add personal notification inbox and preferences.

Revision ID: c25a1b2c3d4e
Revises: b18a0c1d2e3f
"""
from alembic import op
import sqlalchemy as sa

revision: str = "c25a1b2c3d4e"
down_revision: str = "b18a0c1d2e3f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("title", sa.String(150), nullable=False),
        sa.Column("message", sa.String(2000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name="fk_notifications_user_id"),
        sa.UniqueConstraint("user_id", "event_id", name="uq_notifications_user_event"),
        sa.CheckConstraint(
            "type IN ('MATCH_RECEIVED', 'MATCH_CONFIRMED', 'SESSION_PROPOSED', 'POINTS_RECEIVED', 'OTHER')",
            name="ck_notifications_type",
        ),
        sa.CheckConstraint("length(btrim(title)) > 0", name="ck_notifications_title"),
        sa.CheckConstraint("length(btrim(message)) > 0", name="ck_notifications_message"),
    )
    op.create_index(
        "ix_notifications_user_visible_order", "notifications",
        ["user_id", sa.text("created_at DESC"), "id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_notifications_user_unread", "notifications", ["user_id"],
        postgresql_where=sa.text("read_at IS NULL AND deleted_at IS NULL"),
    )
    op.create_table(
        "notification_preferences",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("in_app", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("push", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("email", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("interchanges", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("points", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("general", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE", name="fk_notification_preferences_user_id"),
        sa.CheckConstraint("revision >= 1", name="ck_notification_preferences_revision"),
    )


def downgrade() -> None:
    op.drop_table("notification_preferences")
    op.drop_index("ix_notifications_user_unread", table_name="notifications")
    op.drop_index("ix_notifications_user_visible_order", table_name="notifications")
    op.drop_table("notifications")

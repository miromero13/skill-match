"""Add profile, modality and biometric columns to users and create user_availabilities table (HU-13).

Revision ID: b27f1c8d9e53
Revises: a16e0b7c9d42
"""

from alembic import op
import sqlalchemy as sa

revision: str = "b27f1c8d9e53"
down_revision: str = "a16e0b7c9d42"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("bio", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column("languages", sa.JSON(), nullable=False, server_default=sa.text("'[\"Español\"]'::json")),
    )
    op.add_column(
        "users",
        sa.Column("timezone", sa.String(100), nullable=False, server_default="America/La_Paz"),
    )
    op.add_column(
        "users",
        sa.Column("links", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )
    op.add_column(
        "users",
        sa.Column("exchange_modality", sa.String(20), nullable=False, server_default="VIRTUAL"),
    )
    op.add_column(
        "users",
        sa.Column("presencial_radius_km", sa.Integer(), nullable=False, server_default="10"),
    )
    op.add_column("users", sa.Column("location_label", sa.String(255), nullable=True))
    op.add_column(
        "users",
        sa.Column("buffer_minutes", sa.Integer(), nullable=False, server_default="15"),
    )
    op.add_column(
        "users",
        sa.Column("gcal_synced", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("users", sa.Column("gcal_calendar_email", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("biometric_embedding", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("biometric_enrolled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("biometric_face_hash", sa.String(64), nullable=True))

    op.create_check_constraint(
        "ck_users_exchange_modality",
        "users",
        "exchange_modality IN ('VIRTUAL', 'PRESENCIAL', 'BOTH')",
    )
    op.create_check_constraint(
        "ck_users_presencial_radius_km",
        "users",
        "presencial_radius_km >= 0 AND presencial_radius_km <= 500",
    )

    op.create_table(
        "user_availabilities",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.String(5), nullable=False),
        sa.Column("end_time", sa.String(5), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("modality", sa.String(20), nullable=False, server_default="BOTH"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            ondelete="CASCADE", name="fk_user_availabilities_user_id",
        ),
        sa.CheckConstraint(
            "day_of_week >= 0 AND day_of_week <= 6",
            name="ck_user_availabilities_day_range",
        ),
    )
    op.create_index("ix_user_availabilities_user_id", "user_availabilities", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_availabilities_user_id", table_name="user_availabilities")
    op.drop_table("user_availabilities")

    op.drop_constraint("ck_users_presencial_radius_km", "users", type_="check")
    op.drop_constraint("ck_users_exchange_modality", "users", type_="check")

    op.drop_column("users", "biometric_face_hash")
    op.drop_column("users", "biometric_enrolled_at")
    op.drop_column("users", "biometric_embedding")
    op.drop_column("users", "gcal_calendar_email")
    op.drop_column("users", "gcal_synced")
    op.drop_column("users", "buffer_minutes")
    op.drop_column("users", "location_label")
    op.drop_column("users", "presencial_radius_km")
    op.drop_column("users", "exchange_modality")
    op.drop_column("users", "links")
    op.drop_column("users", "timezone")
    op.drop_column("users", "languages")
    op.drop_column("users", "bio")

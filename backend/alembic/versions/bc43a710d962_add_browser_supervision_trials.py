"""Add isolated SM-43 trial ledger; never alter evaluations or existing records."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "bc43a710d962"
down_revision = "a732bd904c11"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "browser_supervision_trials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("tab_id", postgresql.UUID(as_uuid=True)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("event_count", sa.Integer(), nullable=False),
    )
    op.create_index("uq_browser_trial_open_user", "browser_supervision_trials", ["user_id"], unique=True,
                    postgresql_where=sa.text("closed_at IS NULL"))
    op.create_table(
        "browser_supervision_incidents",
        sa.Column("trial_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("browser_supervision_trials.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.UniqueConstraint("trial_id", "sequence", name="uq_browser_incident_sequence"),
    )
    op.create_index("ix_browser_incident_received", "browser_supervision_incidents", ["trial_id", "received_at"])


def downgrade():
    op.drop_table("browser_supervision_incidents")
    op.drop_table("browser_supervision_trials")

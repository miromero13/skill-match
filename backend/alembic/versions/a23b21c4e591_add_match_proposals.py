"""Add exchange proposals, dismissals and contact messages."""

import sqlalchemy as sa
from alembic import op

revision = "a23b21c4e591"
down_revision = "a20b21c4e590"
branch_labels = None
depends_on = None


def timestamps():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "match_proposals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("match_id", sa.Uuid(), sa.ForeignKey("matches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("proposed_by_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        *timestamps(),
        sa.UniqueConstraint("match_id", "version", name="uq_match_proposal_version"),
        sa.CheckConstraint("version > 0", name="ck_match_proposal_version"),
        sa.CheckConstraint(
            "status IN ('pending', 'superseded', 'accepted', 'declined')",
            name="ck_match_proposal_status",
        ),
    )
    op.create_index("ix_match_proposals_proposed_by_id", "match_proposals", ["proposed_by_id"])
    op.create_table(
        "match_dismissals",
        sa.Column("match_id", sa.Uuid(), sa.ForeignKey("matches.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("member_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        *timestamps(),
    )
    op.create_index("ix_match_dismissals_member_id", "match_dismissals", ["member_id"])
    op.create_table(
        "match_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("match_id", sa.Uuid(), sa.ForeignKey("matches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("body", sa.String(2000), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_match_messages_match_id", "match_messages", ["match_id"])
    op.create_index("ix_match_messages_sender_id", "match_messages", ["sender_id"])


def downgrade() -> None:
    op.drop_table("match_messages")
    op.drop_table("match_dismissals")
    op.drop_table("match_proposals")

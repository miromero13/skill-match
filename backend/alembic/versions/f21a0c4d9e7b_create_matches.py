import sqlalchemy as sa
from alembic import op

revision ="f21a0c4d9e7b"

down_revision = "e31a5d7c9b02"
branch_labels = None 
depends_on = None


def upgrade() -> None:
    # Crea únicamente la tabla nueva de HU-21.
    op.create_table(
        "matches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("member_a_id", sa.Uuid(), nullable=False),
        sa.Column("member_b_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="pending",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["member_a_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_b_id"], ["users.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "member_a_id < member_b_id", name="ck_matches_members_order",
        ),
        sa.UniqueConstraint(
            "member_a_id", "member_b_id", name="uq_matches_members",
        ),
    )

    # El índice de la restricción única ya cubre member_a_id como primer campo.
    op.create_index("ix_matches_member_b_id", "matches", ["member_b_id"])


def downgrade() -> None:
    # Al revertir se elimina la tabla de sugerencias y su índice.
    op.drop_table("matches")

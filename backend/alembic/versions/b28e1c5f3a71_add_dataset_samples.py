"""Add dataset samples table for AI dataset capture tool.

Revision ID: b28e1c5f3a71
Revises: 031f6134f642, a16e0b7c9d42
Create Date: 2026-11-15 19:30:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "b28e1c5f3a71"
down_revision: Union[str, Sequence[str], None] = ("031f6134f642", "a16e0b7c9d42")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dataset_samples",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("discipline", sa.String(length=50), nullable=False),
        sa.Column("challenge", sa.String(length=100), nullable=False),
        sa.Column("hardware_info", sa.String(length=255), nullable=False),
        sa.Column("signed_consent", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("file_format", sa.String(length=10), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("file_hash_sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("uploaded_by_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["uploaded_by_id"],
            ["users.id"],
            ondelete="SET NULL",
            name="fk_dataset_samples_uploaded_by_id",
        ),
        sa.CheckConstraint(
            "file_format IN ('mp4', 'wav', 'py')",
            name="ck_dataset_samples_format",
        ),
        sa.CheckConstraint(
            "signed_consent IS TRUE",
            name="ck_dataset_samples_signed_consent",
        ),
        sa.CheckConstraint(
            "length(file_hash_sha256) = 64",
            name="ck_dataset_samples_hash_length",
        ),
    )
    op.create_index("ix_dataset_samples_discipline", "dataset_samples", ["discipline"])
    op.create_index("ix_dataset_samples_challenge", "dataset_samples", ["challenge"])
    op.create_index("ix_dataset_samples_file_hash_sha256", "dataset_samples", ["file_hash_sha256"])


def downgrade() -> None:
    op.drop_index("ix_dataset_samples_file_hash_sha256", table_name="dataset_samples")
    op.drop_index("ix_dataset_samples_challenge", table_name="dataset_samples")
    op.drop_index("ix_dataset_samples_discipline", table_name="dataset_samples")
    op.drop_table("dataset_samples")

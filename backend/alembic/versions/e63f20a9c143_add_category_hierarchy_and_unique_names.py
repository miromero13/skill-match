"""Add a preserved category hierarchy and normalized scoped name keys.

Revision ID: e63f20a9c143
Revises: d52e19f8b032
"""
import hashlib
import unicodedata

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e63f20a9c143"
down_revision = "d52e19f8b032"
branch_labels = None
depends_on = None


def _key(name):
    # Frozen migration logic, independent of future application helper changes.
    decomposed = unicodedata.normalize("NFKD", name).casefold()
    normalized = " ".join("".join(char for char in decomposed if not unicodedata.combining(char)).split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _backfill(table_name, scope):
    connection = op.get_bind()
    rows = connection.execute(sa.text(f"SELECT id, name, {scope} FROM {table_name}")).mappings().all()
    seen = {}
    values = []
    for row in rows:
        key = _key(row["name"])
        scoped = (row[scope], key)
        if scoped in seen:
            raise RuntimeError(
                f"Duplicate normalized catalog names in {table_name}: {seen[scoped]} and {row['id']}. "
                "Rename conflicting entries before upgrading; no records will be merged or deleted."
            )
        seen[scoped] = row["id"]
        values.append({"id": row["id"], "key": key})
    if values:
        connection.execute(sa.text(f"UPDATE {table_name} SET normalized_name=:key WHERE id=:id"), values)


def upgrade():
    op.add_column("categories", sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_categories_parent", "categories", "categories", ["parent_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_categories_parent_id", "categories", ["parent_id"])
    op.create_check_constraint("ck_categories_not_self_parent", "categories", "parent_id IS NULL OR parent_id <> id")
    for table_name, scope in (("categories", "parent_id"), ("skills", "category_id")):
        op.add_column(table_name, sa.Column("normalized_name", sa.String(64), nullable=True))
        _backfill(table_name, scope)
        op.alter_column(table_name, "normalized_name", nullable=False)
    op.create_unique_constraint("uq_categories_parent_name", "categories", ["parent_id", "normalized_name"])
    op.create_index("uq_categories_root_name", "categories", ["normalized_name"], unique=True, postgresql_where=sa.text("parent_id IS NULL"))
    op.create_unique_constraint("uq_skills_category_name", "skills", ["category_id", "normalized_name"])


def downgrade():
    op.drop_constraint("uq_skills_category_name", "skills", type_="unique")
    op.drop_index("uq_categories_root_name", table_name="categories")
    op.drop_constraint("uq_categories_parent_name", "categories", type_="unique")
    op.drop_column("skills", "normalized_name")
    op.drop_column("categories", "normalized_name")
    op.drop_constraint("ck_categories_not_self_parent", "categories", type_="check")
    op.drop_index("ix_categories_parent_id", table_name="categories")
    op.drop_constraint("fk_categories_parent", "categories", type_="foreignkey")
    op.drop_column("categories", "parent_id")

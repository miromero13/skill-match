"""Normalize the experience column on existing teaching skills tables."""

from alembic import op


revision = "e31a5d7c9b02"
down_revision = "d25e4f6a7b8c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Older copies of f69de0a4b8f0 created the misspelled column.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_attribute
                WHERE attrelid = 'user_teaching_skills'::regclass
                  AND attname = 'years_of_experence' AND NOT attisdropped
            ) THEN
                ALTER TABLE user_teaching_skills
                    RENAME COLUMN years_of_experence TO years_of_experience;
            END IF;
        END;
        $$;
    """)


def downgrade() -> None:
    # The parent schema also uses the canonical spelling on fresh databases.
    pass

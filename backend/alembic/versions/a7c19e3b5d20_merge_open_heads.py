"""Merge the open heads before browser-supervision schema changes.

c3bea441869b is the head that carries the browser-supervision tables.
Kept free of operations so `downgrade -1` from later revisions is unambiguous.

Revision ID: a7c19e3b5d20
Revises: c3bea441869b, ce51f995031a, f6a39d2c801b
"""

revision = "a7c19e3b5d20"
down_revision = ("c3bea441869b", "ce51f995031a", "f6a39d2c801b")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass

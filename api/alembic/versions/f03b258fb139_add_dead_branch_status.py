"""add dead branch status

Revision ID: f03b258fb139
Revises: a7c070e0889d
"""

from alembic import op


revision = "f03b258fb139"
down_revision = "a7c070e0889d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE branchstatus "
        "ADD VALUE IF NOT EXISTS 'DEAD'"
    )


def downgrade() -> None:
    pass
"""Add ui_locale column to jobs table

Revision ID: 0017
Revises: 0016
Create Date: 2026-03-28

"""
from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("ui_locale", sa.String(5), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "ui_locale")

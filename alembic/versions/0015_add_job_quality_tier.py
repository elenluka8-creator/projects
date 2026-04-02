"""Add quality_tier column to jobs table

Revision ID: 0015
Revises: 0014
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa


revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("quality_tier", sa.String(20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("jobs", "quality_tier")

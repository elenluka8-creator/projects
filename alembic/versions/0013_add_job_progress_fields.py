"""Add durable progress fields to jobs (FEAT-PROGRESS / DEC-010)

Revision ID: 0013
Revises: 0012
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa


revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jobs",
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("jobs", sa.Column("pipeline_stage", sa.String(32), nullable=True))
    op.add_column("jobs", sa.Column("eta_seconds_remaining", sa.Integer(), nullable=True))
    op.add_column(
        "jobs",
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("jobs", "processing_started_at")
    op.drop_column("jobs", "eta_seconds_remaining")
    op.drop_column("jobs", "pipeline_stage")
    op.drop_column("jobs", "progress_percent")

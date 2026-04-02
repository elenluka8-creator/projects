"""Add translation config fields to jobs table

Revision ID: 0012
Revises: 0011
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("translation_style", sa.String(20), nullable=True))
    op.add_column("jobs", sa.Column("user_level", sa.String(5), nullable=True))
    op.add_column("jobs", sa.Column("explanation_depth", sa.String(20), nullable=True))
    op.add_column(
        "jobs",
        sa.Column("client_submission_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_jobs_client_submission_id", "jobs", ["client_submission_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_client_submission_id", table_name="jobs")
    op.drop_column("jobs", "client_submission_id")
    op.drop_column("jobs", "explanation_depth")
    op.drop_column("jobs", "user_level")
    op.drop_column("jobs", "translation_style")

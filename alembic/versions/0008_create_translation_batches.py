"""Create translation_batches table

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "translation_batches",
        sa.Column("batch_id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("job_runs.job_run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("jobs.job_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("batch_index", sa.Integer(), nullable=False),
        sa.Column("chapter_ref", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("input_hash", sa.String(), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_translation_batches_job_run_id", "translation_batches", ["job_run_id"])
    op.create_index("ix_translation_batches_job_id", "translation_batches", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_translation_batches_job_id", table_name="translation_batches")
    op.drop_index("ix_translation_batches_job_run_id", table_name="translation_batches")
    op.drop_table("translation_batches")

"""Create job_consistency_snapshots table

Revision ID: 0016
Revises: 0015
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_consistency_snapshots",
        sa.Column("job_id", sa.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("batch_index", sa.Integer(), nullable=False, default=0),
        sa.Column("terminology", JSONB(), nullable=False, server_default="{}"),
        sa.Column("entities", JSONB(), nullable=False, server_default="{}"),
        sa.Column("chapter_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("job_consistency_snapshots")

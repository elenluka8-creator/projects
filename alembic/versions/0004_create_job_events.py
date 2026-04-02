"""Create job_events table

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, UUID

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_events",
        sa.Column("event_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", UUID(as_uuid=True), nullable=False),
        sa.Column("job_run_id", UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("stage", sa.String(), nullable=True),
        sa.Column("batch_index", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("error_class", sa.String(), nullable=True),
        sa.Column("payload", JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_job_events_job_id", "job_events", ["job_id"], unique=False)
    op.create_index("ix_job_events_user_id", "job_events", ["user_id"], unique=False)
    op.create_index(
        "ix_job_events_event_type", "job_events", ["event_type"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_job_events_event_type", table_name="job_events")
    op.drop_index("ix_job_events_user_id", table_name="job_events")
    op.drop_index("ix_job_events_job_id", table_name="job_events")
    op.drop_table("job_events")

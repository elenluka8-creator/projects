"""Create cost_ledger_entries table

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-14

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cost_ledger_entries",
        sa.Column("entry_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", UUID(as_uuid=True), nullable=False),
        sa.Column("job_run_id", UUID(as_uuid=True), nullable=True),
        sa.Column("batch_index", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("estimated_cost_usd", sa.Numeric(10, 6), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_cost_ledger_entries_job_id",
        "cost_ledger_entries",
        ["job_id"],
        unique=False,
    )
    op.create_index(
        "ix_cost_ledger_entries_job_run_id",
        "cost_ledger_entries",
        ["job_run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_cost_ledger_entries_job_run_id", table_name="cost_ledger_entries")
    op.drop_index("ix_cost_ledger_entries_job_id", table_name="cost_ledger_entries")
    op.drop_table("cost_ledger_entries")

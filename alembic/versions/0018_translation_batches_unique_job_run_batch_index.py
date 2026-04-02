"""Deduplicate translation_batches then add unique (job_run_id, batch_index)

Revision ID: 0018
Revises: 0017
Create Date: 2026-03-28

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Keep one row per (job_run_id, batch_index): prefer completed, then latest completed_at.
    op.execute(
        """
        DELETE FROM translation_batches tb
        WHERE tb.batch_id IN (
            SELECT batch_id FROM (
                SELECT batch_id,
                       ROW_NUMBER() OVER (
                           PARTITION BY job_run_id, batch_index
                           ORDER BY
                             CASE WHEN status = 'completed' THEN 0 ELSE 1 END,
                             completed_at DESC NULLS LAST,
                             created_at DESC
                       ) AS rn
                FROM translation_batches
            ) sub
            WHERE sub.rn > 1
        );
        """
    )
    op.create_unique_constraint(
        "uq_translation_batches_job_run_batch_index",
        "translation_batches",
        ["job_run_id", "batch_index"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_translation_batches_job_run_batch_index",
        "translation_batches",
        type_="unique",
    )

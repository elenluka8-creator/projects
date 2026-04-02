"""Create precheck_results table

Revision ID: 0011
Revises: 0010
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "precheck_results",
        sa.Column("precheck_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("detected_language", sa.String(20), nullable=True),
        sa.Column("language_confidence", sa.Float(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("chapter_count", sa.Integer(), nullable=True),
        sa.Column("has_images", sa.Boolean(), nullable=True),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("precheck_id"),
        sa.ForeignKeyConstraint(
            ["artifact_id"], ["artifacts.artifact_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.user_id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("artifact_id", name="uq_precheck_results_artifact_id"),
    )
    op.create_index("ix_precheck_results_artifact_id", "precheck_results", ["artifact_id"])
    op.create_index("ix_precheck_results_user_id", "precheck_results", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_precheck_results_user_id", table_name="precheck_results")
    op.drop_index("ix_precheck_results_artifact_id", table_name="precheck_results")
    op.drop_table("precheck_results")

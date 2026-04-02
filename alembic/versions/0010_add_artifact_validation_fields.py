"""Add validation fields to artifacts table

Revision ID: 0010
Revises: 0009
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "artifacts",
        sa.Column("content_sha256", sa.String(64), nullable=True),
    )
    op.add_column(
        "artifacts",
        sa.Column("mime_type", sa.String(255), nullable=True),
    )
    op.add_column(
        "artifacts",
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("artifacts", "validated_at")
    op.drop_column("artifacts", "mime_type")
    op.drop_column("artifacts", "content_sha256")

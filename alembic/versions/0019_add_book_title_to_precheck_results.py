"""Add book_title and book_author to precheck_results

Revision ID: 0019
Revises: 0018
Create Date: 2026-04-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "precheck_results",
        sa.Column("book_title", sa.String(), nullable=True),
    )
    op.add_column(
        "precheck_results",
        sa.Column("book_author", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("precheck_results", "book_author")
    op.drop_column("precheck_results", "book_title")

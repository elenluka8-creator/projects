"""Create app_settings key-value table

Revision ID: 0014
Revises: 0013
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa


revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    # Seed the initial_credit_grant setting with the default value of 0.
    op.execute("INSERT INTO app_settings (key, value) VALUES ('initial_credit_grant', '0')")


def downgrade() -> None:
    op.drop_table("app_settings")

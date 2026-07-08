"""verification codes

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-08
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.types import GUID

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "verification_codes",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("code", sa.String(10), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_verification_codes_email", "verification_codes", ["email"])


def downgrade() -> None:
    op.drop_index("ix_verification_codes_email", table_name="verification_codes")
    op.drop_table("verification_codes")

"""oauth identities: nullable password + oauth_identities table

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-08
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.types import GUID

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.alter_column("password_hash", existing_type=sa.Text(), nullable=True)

    op.create_table(
        "oauth_identities",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column(
            "user_id",
            GUID(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_account_id", sa.String(255), nullable=False),
        sa.Column("provider_login", sa.String(255), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "provider", "provider_account_id", name="uq_oauth_provider_account"
        ),
    )
    op.create_index("ix_oauth_identities_user_id", "oauth_identities", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_oauth_identities_user_id", table_name="oauth_identities")
    op.drop_table("oauth_identities")
    with op.batch_alter_table("users") as batch:
        batch.alter_column("password_hash", existing_type=sa.Text(), nullable=False)

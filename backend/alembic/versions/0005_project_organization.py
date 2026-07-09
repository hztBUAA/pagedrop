"""project organization: folder_path, status, deleted_at

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-09

All columns are additive and nullable (or carry a server default), so old
application code that predates them keeps working against the same database.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("folder_path", sa.String(500), nullable=True))
    op.add_column(
        "projects",
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="active",
        ),
    )
    op.add_column(
        "projects",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "deleted_at")
    op.drop_column("projects", "status")
    op.drop_column("projects", "folder_path")

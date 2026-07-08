"""assets and comments

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-08
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.types import GUID

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("workspace_id", GUID(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("storage_key", sa.String(400), nullable=False),
        sa.Column("original_name", sa.String(300), nullable=True),
        sa.Column("created_by_user_id", GUID(), nullable=True),
        sa.Column("created_by_token_id", GUID(), nullable=True),
        sa.Column("created_by_source", sa.String(20), nullable=False, server_default="web"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "sha256", name="uq_workspace_asset_sha256"),
    )
    op.create_index("ix_assets_workspace_id", "assets", ["workspace_id"])
    op.create_index("ix_assets_project_id", "assets", ["project_id"])
    op.create_index("ix_assets_sha256", "assets", ["sha256"])

    op.create_table(
        "comments",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("thread_root_id", GUID(), nullable=True),
        sa.Column("anchor_version_number", sa.Integer(), nullable=True),
        sa.Column("anchor_quote", sa.Text(), nullable=True),
        sa.Column("anchor_prefix", sa.String(200), nullable=True),
        sa.Column("anchor_suffix", sa.String(200), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("author_user_id", GUID(), nullable=True),
        sa.Column("author_token_id", GUID(), nullable=True),
        sa.Column("author_source", sa.String(20), nullable=False, server_default="web"),
        sa.Column("author_display", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_user_id", GUID(), nullable=True),
    )
    op.create_index("ix_comments_project_id", "comments", ["project_id"])
    op.create_index("ix_comments_thread_root_id", "comments", ["thread_root_id"])


def downgrade() -> None:
    op.drop_index("ix_comments_thread_root_id", table_name="comments")
    op.drop_index("ix_comments_project_id", table_name="comments")
    op.drop_table("comments")
    op.drop_index("ix_assets_sha256", table_name="assets")
    op.drop_index("ix_assets_project_id", table_name="assets")
    op.drop_index("ix_assets_workspace_id", table_name="assets")
    op.drop_table("assets")

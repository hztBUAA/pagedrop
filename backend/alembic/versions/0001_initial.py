"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-05
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.types import GUID, JSONType

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("name", sa.String(200)),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("avatar_url", sa.Text()),
        sa.Column("is_platform_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "workspaces",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False, unique=True),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("owner_user_id", GUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workspaces_slug", "workspaces", ["slug"])

    op.create_table(
        "workspace_members",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("workspace_id", GUID(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_user"),
    )

    op.create_table(
        "projects",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("workspace_id", GUID(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("default_content_type", sa.String(20), nullable=False),
        sa.Column("visibility", sa.String(20), nullable=False, server_default="unlisted"),
        sa.Column("latest_version_id", GUID()),
        sa.Column("created_by_user_id", GUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "slug", name="uq_workspace_slug"),
    )
    op.create_index("ix_projects_workspace_id", "projects", ["workspace_id"])
    op.create_index("ix_projects_slug", "projects", ["slug"])

    op.create_table(
        "page_versions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(20), nullable=False),
        sa.Column("source_content", sa.Text(), nullable=False),
        sa.Column("rendered_html", sa.Text()),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("changelog", sa.Text()),
        sa.Column("created_by_user_id", GUID(), sa.ForeignKey("users.id")),
        sa.Column("created_by_token_id", GUID()),
        sa.Column("created_by_source", sa.String(20), nullable=False),
        sa.Column("secret_scan_status", sa.String(20), nullable=False, server_default="passed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "version_number", name="uq_project_version"),
    )
    op.create_index("ix_page_versions_project_id", "page_versions", ["project_id"])

    op.create_table(
        "api_tokens",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("workspace_id", GUID(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("created_by_user_id", GUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("token_prefix", sa.String(40), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("scopes", JSONType(), nullable=False),
        sa.Column("project_allowlist", JSONType()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_ip", sa.String(64)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_api_tokens_workspace_id", "api_tokens", ["workspace_id"])
    op.create_index("ix_api_tokens_token_prefix", "api_tokens", ["token_prefix"])
    op.create_index("ix_api_tokens_token_hash", "api_tokens", ["token_hash"])

    op.create_table(
        "share_links",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("project_id", GUID(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("version_id", GUID(), sa.ForeignKey("page_versions.id")),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("access_type", sa.String(20), nullable=False),
        sa.Column("password_hash", sa.Text()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("max_views", sa.Integer()),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by_user_id", GUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_share_links_project_id", "share_links", ["project_id"])
    op.create_index("ix_share_links_token_hash", "share_links", ["token_hash"])

    op.create_table(
        "audit_logs",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("workspace_id", GUID(), sa.ForeignKey("workspaces.id")),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id")),
        sa.Column("token_id", GUID(), sa.ForeignKey("api_tokens.id")),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("target_type", sa.String(40), nullable=False),
        sa.Column("target_id", GUID()),
        sa.Column("ip", sa.String(64)),
        sa.Column("user_agent", sa.Text()),
        sa.Column("metadata", JSONType()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_workspace_id", "audit_logs", ["workspace_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("share_links")
    op.drop_table("api_tokens")
    op.drop_table("page_versions")
    op.drop_table("projects")
    op.drop_table("workspace_members")
    op.drop_table("workspaces")
    op.drop_table("users")

export interface User {
  id: string;
  email: string;
  name: string | null;
  avatar_url: string | null;
  is_platform_admin: boolean;
  created_at: string;
}

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  type: string;
  owner_user_id: string;
  created_at: string;
  role: string;
}

export interface Member {
  id: string;
  user_id: string;
  workspace_id: string;
  role: string;
  created_at: string;
}

export interface Project {
  id: string;
  workspace_id: string;
  slug: string;
  title: string;
  description: string | null;
  default_content_type: string;
  visibility: string;
  latest_version_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface VersionSummary {
  id: string;
  version_number: number;
  title: string;
  content_type: string;
  changelog: string | null;
  created_by_source: string;
  created_at: string;
}

export interface Version extends VersionSummary {
  project_id: string;
  source_content: string;
  rendered_html: string | null;
  summary: string | null;
  secret_scan_status: string;
}

export interface PublishRequest {
  workspace_slug: string;
  slug: string;
  title: string;
  content_type: string;
  content: string;
  visibility: string;
  message?: string | null;
  summary?: string | null;
  source?: string;
  force?: boolean;
}

export interface PublishResponse {
  project_id: string;
  version_id: string;
  slug: string;
  version: number;
  latest_url: string;
  version_url: string;
  visibility: string;
  secret_scan_status: string;
}

export interface ApiToken {
  id: string;
  workspace_id: string;
  name: string;
  token_prefix: string;
  scopes: string[];
  project_allowlist: string[] | null;
  expires_at: string | null;
  last_used_at: string | null;
  last_used_ip: string | null;
  revoked_at: string | null;
  created_at: string;
}

export interface TokenCreateResponse {
  token: string;
  token_prefix: string;
  warning: string;
  token_info: ApiToken;
}

export interface ShareLink {
  id: string;
  project_id: string;
  version_id: string | null;
  access_type: string;
  has_password: boolean;
  expires_at: string | null;
  max_views: number | null;
  view_count: number;
  revoked_at: string | null;
  created_at: string;
}

export interface ShareLinkCreateResponse {
  share_url: string;
  access_type: string;
  expires_at: string | null;
  link: ShareLink;
}

export interface PublicPage {
  workspace_slug: string;
  project_slug: string;
  project_id: string;
  title: string;
  visibility: string;
  content_type: string;
  source_content: string;
  rendered_html: string | null;
  version_number: number;
  summary: string | null;
  is_latest: boolean;
  noindex: boolean;
  updated_at: string;
}

export interface SecretFinding {
  rule: string;
  preview: string;
  line: number;
}

export interface Asset {
  id: string;
  workspace_id: string;
  project_id: string | null;
  sha256: string;
  content_type: string;
  byte_size: number;
  width: number | null;
  height: number | null;
  original_name: string | null;
  created_at: string;
  ref: string;
}

export interface Comment {
  id: string;
  project_id: string;
  thread_root_id: string | null;
  anchor_version_number: number | null;
  anchor_quote: string | null;
  anchor_prefix: string | null;
  anchor_suffix: string | null;
  body: string;
  status: string;
  author_source: string;
  author_display: string | null;
  created_at: string;
  resolved_at: string | null;
}

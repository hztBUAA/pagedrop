import { api } from "./client";
import type {
  ApiToken,
  Asset,
  Comment,
  Member,
  Project,
  PublicPage,
  PublishRequest,
  PublishResponse,
  ShareLink,
  ShareLinkCreateResponse,
  TokenCreateResponse,
  User,
  Version,
  VersionSummary,
  Workspace,
} from "./types";

export const authApi = {
  requestCode: (email: string, purpose: "register" | "reset" = "register") =>
    api.post<{ status: string }>("/auth/request-code", { email, purpose }),
  register: (email: string, password: string, code: string, name?: string) =>
    api.post<User>("/auth/register", { email, password, code, name }),
  resetPassword: (email: string, code: string, newPassword: string) =>
    api.post<User>("/auth/reset-password", { email, code, new_password: newPassword }),
  login: (email: string, password: string) =>
    api.post<User>("/auth/login", { email, password }),
  logout: () => api.post<{ status: string }>("/auth/logout"),
  me: () => api.get<User>("/auth/me"),
  oauthProviders: () => api.get<{ providers: string[] }>("/auth/oauth/providers"),
  oauthStart: (provider: string) =>
    api.get<{ authorize_url: string }>(`/auth/oauth/${provider}/start`),
  oauthCallback: (code: string, state: string) =>
    api.post<User>("/auth/oauth/callback", { code, state }),
};

export const workspaceApi = {
  list: () => api.get<Workspace[]>("/workspaces"),
  create: (name: string) => api.post<Workspace>("/workspaces", { name }),
  get: (id: string) => api.get<Workspace>(`/workspaces/${id}`),
  members: (id: string) => api.get<Member[]>(`/workspaces/${id}/members`),
  addMember: (id: string, email: string, role: string) =>
    api.post<Member>(`/workspaces/${id}/members`, { email, role }),
};

export const projectApi = {
  list: (
    workspaceId: string,
    opts?: { q?: string; folder?: string; status?: string; limit?: number; offset?: number },
  ) => {
    const params = new URLSearchParams({ workspace_id: workspaceId });
    if (opts?.q) params.set("q", opts.q);
    if (opts?.folder) params.set("folder", opts.folder);
    if (opts?.status) params.set("status", opts.status);
    if (opts?.limit != null) params.set("limit", String(opts.limit));
    if (opts?.offset != null) params.set("offset", String(opts.offset));
    return api.get<Project[]>(`/projects?${params.toString()}`);
  },
  folders: (workspaceId: string) =>
    api.get<string[]>(`/projects/folders?workspace_id=${workspaceId}`),
  publish: (payload: PublishRequest) =>
    api.post<PublishResponse>("/projects.publish", payload),
  get: (ws: string, slug: string) =>
    api.get<Project>(`/projects/${ws}/${slug}`),
  versions: (ws: string, slug: string) =>
    api.get<VersionSummary[]>(`/projects/${ws}/${slug}/versions`),
  version: (ws: string, slug: string, version: number) =>
    api.get<Version>(`/projects/${ws}/${slug}/versions/${version}`),
  updateSettings: (
    ws: string,
    slug: string,
    payload: { title?: string; description?: string; visibility?: string; folder_path?: string | null },
  ) => api.patch<Project>(`/projects/${ws}/${slug}/settings`, payload),
  archive: (ws: string, slug: string) =>
    api.post<Project>(`/projects/${ws}/${slug}/archive`),
  unarchive: (ws: string, slug: string) =>
    api.post<Project>(`/projects/${ws}/${slug}/unarchive`),
  del: (ws: string, slug: string) =>
    api.del<{ status: string }>(`/projects/${ws}/${slug}`),
};

export const tokenApi = {
  list: (workspaceId: string) =>
    api.get<ApiToken[]>(`/tokens?workspace_id=${workspaceId}`),
  create: (payload: {
    workspace_slug: string;
    name: string;
    scopes: string[];
    project_allowlist?: string[] | null;
    expires_at?: string | null;
  }) => api.post<TokenCreateResponse>("/tokens", payload),
  revoke: (id: string) => api.del<{ status: string }>(`/tokens/${id}`),
};

export const shareApi = {
  list: (ws: string, slug: string) =>
    api.get<ShareLink[]>(`/projects/${ws}/${slug}/share-links`),
  create: (
    ws: string,
    slug: string,
    payload: {
      access_type: string;
      version?: number | null;
      password?: string | null;
      expires_at?: string | null;
      max_views?: number | null;
    },
  ) =>
    api.post<ShareLinkCreateResponse>(
      `/projects/${ws}/${slug}/share-links`,
      payload,
    ),
  revoke: (id: string) => api.del<{ status: string }>(`/share-links/${id}`),
};

export const assetApi = {
  upload: (workspaceSlug: string, projectSlug: string | null, file: File) => {
    const form = new FormData();
    form.append("file", file);
    form.append("workspace_slug", workspaceSlug);
    if (projectSlug) form.append("project_slug", projectSlug);
    return api.upload<Asset>("/assets", form);
  },
};

export const commentApi = {
  list: (
    ws: string,
    slug: string,
    status?: "open" | "resolved",
    shareToken?: string | null,
  ) => {
    const qs = new URLSearchParams();
    if (status) qs.set("status", status);
    if (shareToken) qs.set("share_token", shareToken);
    const q = qs.toString();
    return api.get<Comment[]>(`/projects/${ws}/${slug}/comments${q ? `?${q}` : ""}`);
  },
  create: (
    ws: string,
    slug: string,
    payload: {
      body: string;
      thread_root_id?: string | null;
      anchor_version_number?: number | null;
      anchor_quote?: string | null;
      anchor_prefix?: string | null;
      anchor_suffix?: string | null;
    },
    shareToken?: string | null,
  ) =>
    api.post<Comment>(
      `/projects/${ws}/${slug}/comments${
        shareToken ? `?share_token=${encodeURIComponent(shareToken)}` : ""
      }`,
      payload,
    ),
  resolve: (id: string) => api.post<Comment>(`/comments/${id}/resolve`),
  reopen: (id: string) => api.post<Comment>(`/comments/${id}/reopen`),
  del: (id: string) => api.del<{ status: string }>(`/comments/${id}`),
};

export const publicApi = {
  latest: (ws: string, slug: string) =>
    api.get<PublicPage>(`/public/projects/${ws}/${slug}/latest`),
  version: (ws: string, slug: string, version: number) =>
    api.get<PublicPage>(`/public/projects/${ws}/${slug}/versions/${version}`),
  share: (token: string) => api.get<PublicPage>(`/public/share/${token}`),
  verifyPassword: (token: string, password: string) =>
    api.post<PublicPage>(`/public/share/${token}/verify-password`, { password }),
};

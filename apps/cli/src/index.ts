#!/usr/bin/env node
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { basename, dirname, extname, join, resolve } from "node:path";

import { Command } from "commander";

import { ApiClient, ApiError } from "./api.js";
import {
  GITHUB_CLIENT_ID,
  githubDeviceFlow,
  mintTokenAndStore,
  randomPassword,
  resolveValue,
} from "./auth.js";
import { resolveProfile, upsertProfile, configPath, type Profile } from "./config.js";
import {
  EXT_BY_MIME,
  extractAssetIds,
  extractLocalImageRefs,
  mimeForPath,
  replaceRef,
} from "./media.js";

const DEFAULT_URL = "https://pagedrop.justinhuang.top";
const SHARE_PREFIX = "pds_";

interface AssetResponse {
  id: string;
  ref: string;
  content_type: string;
}

interface CommentResponse {
  id: string;
  thread_root_id: string | null;
  status: string;
  body: string;
  author_display: string | null;
  anchor_quote: string | null;
  anchor_version_number: number | null;
  created_at: string;
}

interface Whoami {
  type: string;
  email: string | null;
  token_id: string | null;
  token_name: string | null;
  workspace_id: string | null;
  workspace_slug?: string | null;
  workspace_name?: string | null;
  scopes: string[];
}

interface PublishResponse {
  slug: string;
  version: number;
  latest_url: string;
  version_url: string;
  visibility: string;
  secret_scan_status: string;
}

function clientFromProfile(profileName?: string): ApiClient {
  const { profile } = resolveProfile(profileName);
  return new ApiClient(profile.baseUrl, profile.token);
}

function contentTypeFromPath(path: string): string {
  const ext = extname(path).toLowerCase();
  if (ext === ".html" || ext === ".htm") return "safe_html";
  return "markdown";
}

function readInput(file: string | undefined): string {
  if (!file || file === "-") return readFileSync(0, "utf8");
  return readFileSync(file, "utf8");
}

/**
 * Upload local images referenced by the content and rewrite each reference to a
 * stable `pagedrop://asset/<id>` ref. Remote/data/pagedrop refs are left as-is.
 */
async function uploadLocalImages(
  client: ApiClient,
  content: string,
  baseDir: string,
  workspace: string,
  slug: string,
): Promise<{ content: string; count: number }> {
  let out = content;
  let count = 0;
  for (const ref of extractLocalImageRefs(content)) {
    const abs = resolve(baseDir, ref);
    if (!existsSync(abs)) {
      process.stderr.write(`warning: image not found, left as-is: ${ref}\n`);
      continue;
    }
    const mime = mimeForPath(ref);
    if (!mime) {
      process.stderr.write(`warning: unsupported image type, left as-is: ${ref}\n`);
      continue;
    }
    const bytes = readFileSync(abs);
    const form = new FormData();
    form.append("file", new Blob([bytes], { type: mime }), basename(ref));
    form.append("workspace_slug", workspace);
    form.append("project_slug", slug);
    const asset = await client.postForm<AssetResponse>("/assets", form);
    out = replaceRef(out, ref, asset.ref);
    count += 1;
  }
  return { content: out, count };
}

function fail(message: string): never {
  process.stderr.write(`error: ${message}\n`);
  process.exit(1);
}

function reportApiError(err: unknown): never {
  if (err instanceof ApiError) {
    if (err.detail && typeof err.detail === "object") {
      const detail = err.detail as Record<string, unknown>;
      if (detail.error === "secret_detected") {
        const findings = Array.isArray(detail.findings) ? detail.findings : [];
        process.stderr.write(
          `error: publish blocked — ${findings.length} potential secret(s) detected.\n`,
        );
        for (const f of findings as Array<Record<string, unknown>>) {
          process.stderr.write(`  - ${f.type ?? "secret"}: ${f.preview ?? ""}\n`);
        }
        process.stderr.write("Re-run with --force to publish anyway.\n");
        process.exit(2);
      }
      fail(`${err.status} ${JSON.stringify(err.detail)}`);
    }
    fail(`${err.status} ${String(err.detail)}`);
  }
  fail((err as Error).message ?? String(err));
}

const program = new Command();
program
  .name("pagedrop")
  .description("Publish Markdown / HTML / agent artifacts to PageDrop")
  .version("0.1.0")
  .option("-p, --profile <name>", "credential profile to use");

program
  .command("login")
  .description("Log in and store a credential. With --token, stores an existing API token; with --email, logs in with a password and mints a scoped token.")
  .option("-t, --token <token>", "existing PageDrop API token (pd_live_...)")
  .option("-e, --email <email>", "account email (password login → auto-mint token)")
  .option("--password <password>", "account password (prompted if omitted on a TTY)")
  .option("-w, --workspace <slug>", "workspace to scope the minted token to")
  .option("--token-name <name>", "name for the minted token", "cli")
  .option("-u, --url <url>", "server base URL", DEFAULT_URL)
  .option("-n, --name <name>", "profile name", "default")
  .action(async (opts) => {
    // Mode 1: store an existing API token (original behavior).
    if (opts.token) {
      const client = new ApiClient(opts.url, opts.token);
      let who: Whoami;
      try {
        who = await client.get<Whoami>("/auth/whoami");
      } catch (err) {
        reportApiError(err);
      }
      if (who.type !== "token") {
        fail("that credential is not an API token");
      }
      const profile: Profile = {
        baseUrl: opts.url,
        token: opts.token,
        workspace: who.workspace_id ?? undefined,
      };
      upsertProfile(opts.name, profile);
      process.stdout.write(
        `Logged in as token "${who.token_name ?? who.token_id}" ` +
          `(scopes: ${who.scopes.join(", ") || "none"}).\n` +
          `Saved to profile "${opts.name}" at ${configPath()}.\n`,
      );
      return;
    }

    // Mode 2: email + password → session → mint token.
    try {
      const email = await resolveValue(
        opts.email,
        "Email: ",
        "provide --email (or --token for an existing token)",
      );
      const password = await resolveValue(
        opts.password,
        "Password: ",
        "provide --password (or run on a terminal to be prompted)",
        true,
      );
      const client = new ApiClient(opts.url, "");
      await client.post("/auth/login", { email, password });
      if (!client.hasSession()) fail("login did not establish a session");
      await mintTokenAndStore(client, {
        baseUrl: opts.url,
        workspaceSlug: opts.workspace,
        tokenName: opts.tokenName,
        profileName: opts.name,
      });
    } catch (err) {
      reportApiError(err);
    }
  });

program
  .command("register")
  .description("Create a PageDrop account from the terminal (email verification code) and mint a scoped token.")
  .requiredOption("-e, --email <email>", "account email")
  .option("--code <code>", "email verification code (omit to request one)")
  .option("--password <password>", "account password (prompted/generated if omitted)")
  .option("--generate-password", "generate a strong random password and print it once", false)
  .option("--display-name <name>", "display name for the account")
  .option("-w, --workspace <slug>", "workspace to scope the minted token to")
  .option("--token-name <name>", "name for the minted token", "cli")
  .option("-u, --url <url>", "server base URL", DEFAULT_URL)
  .option("-n, --name <name>", "profile name", "default")
  .action(async (opts) => {
    try {
      const client = new ApiClient(opts.url, "");

      // Step 1: no code yet → request one by email.
      if (!opts.code) {
        await client.post("/auth/request-code", { email: opts.email, purpose: "register" });
        if (!process.stdin.isTTY) {
          process.stdout.write(
            `A verification code was emailed to ${opts.email}.\n` +
              `Re-run with the code:  pagedrop register --email ${opts.email} --code <CODE> [--generate-password]\n`,
          );
          return;
        }
        process.stdout.write(`A verification code was emailed to ${opts.email}.\n`);
        opts.code = await resolveValue(undefined, "Verification code: ", "verification code required");
      }

      // Step 2: resolve a password.
      let password: string = opts.password;
      if (!password && opts.generatePassword) {
        password = randomPassword();
        process.stdout.write(`Generated password (store it, needed for web login): ${password}\n`);
      }
      if (!password) {
        password = await resolveValue(
          undefined,
          "Choose a password (min 8 chars): ",
          "provide --password or --generate-password",
          true,
        );
      }

      // Step 3: register (sets session cookie) → mint token.
      await client.post("/auth/register", {
        email: opts.email,
        password,
        code: opts.code,
        name: opts.displayName ?? null,
      });
      if (!client.hasSession()) fail("registration did not establish a session");
      await mintTokenAndStore(client, {
        baseUrl: opts.url,
        workspaceSlug: opts.workspace,
        tokenName: opts.tokenName,
        profileName: opts.name,
      });
    } catch (err) {
      reportApiError(err);
    }
  });

const auth = program.command("auth").description("Authenticate via an identity provider");

auth
  .command("github")
  .description("Log in with GitHub (OAuth device flow) and mint a scoped token — no browser typing of passwords.")
  .option("--client-id <id>", "GitHub OAuth App client_id", GITHUB_CLIENT_ID)
  .option("--no-browser", "do not attempt to open a browser automatically")
  .option("-w, --workspace <slug>", "workspace to scope the minted token to")
  .option("--token-name <name>", "name for the minted token", "cli")
  .option("-u, --url <url>", "server base URL", DEFAULT_URL)
  .option("-n, --name <name>", "profile name", "default")
  .action(async (opts) => {
    try {
      const githubToken = await githubDeviceFlow(opts.clientId, opts.browser !== false);
      const client = new ApiClient(opts.url, "");
      await client.post("/auth/github", { access_token: githubToken });
      if (!client.hasSession()) fail("GitHub login did not establish a session");
      await mintTokenAndStore(client, {
        baseUrl: opts.url,
        workspaceSlug: opts.workspace,
        tokenName: opts.tokenName,
        profileName: opts.name,
      });
    } catch (err) {
      reportApiError(err);
    }
  });

program
  .command("whoami")
  .description("Show the identity behind the current credential")
  .action(async () => {
    try {
      const who = await clientFromProfile(program.opts().profile).get<Whoami>("/auth/whoami");
      process.stdout.write(JSON.stringify(who, null, 2) + "\n");
    } catch (err) {
      reportApiError(err);
    }
  });

program
  .command("publish")
  .description("Publish a file (or stdin) as a new immutable version")
  .argument("[file]", "path to content file, or '-' for stdin")
  .requiredOption("-w, --workspace <slug>", "target workspace slug")
  .requiredOption("-s, --slug <slug>", "project slug")
  .option("-T, --title <title>", "page title (defaults to slug)")
  .option("-c, --content-type <type>", "markdown | safe_html | sandbox_html")
  .option("-v, --visibility <visibility>", "public | unlisted | private", "private")
  .option("-m, --message <message>", "changelog message for this version")
  .option("--summary <summary>", "short summary")
  .option("--no-images", "do not upload/rewrite local images referenced in the content")
  .option("--force", "publish even if secrets are detected", false)
  .action(async (file, opts) => {
    const content = readInput(file);
    const contentType = opts.contentType ?? (file ? contentTypeFromPath(file) : "markdown");
    const title = opts.title ?? (file ? basename(file, extname(file)) : opts.slug);
    const client = clientFromProfile(program.opts().profile);

    let finalContent = content;
    // Only scan for local images when reading from a real file (relative paths
    // are resolved against its directory); stdin has no base directory.
    if (opts.images !== false && file && file !== "-") {
      try {
        const res = await uploadLocalImages(
          client,
          content,
          dirname(resolve(file)),
          opts.workspace,
          opts.slug,
        );
        finalContent = res.content;
        if (res.count > 0) {
          process.stdout.write(`Uploaded ${res.count} image(s).\n`);
        }
      } catch (err) {
        reportApiError(err);
      }
    } else if (opts.images !== false) {
      // stdin / no base directory: local images can't be resolved or uploaded.
      // Warn loudly instead of silently publishing broken relative-path images.
      const stray = extractLocalImageRefs(content);
      if (stray.length > 0) {
        process.stderr.write(
          `warning: ${stray.length} local image reference(s) will NOT be uploaded ` +
            `because content was read from stdin (no base directory):\n`,
        );
        for (const ref of stray) process.stderr.write(`  - ${ref}\n`);
        process.stderr.write(
          "These will render as broken images. Write the content to a file and " +
            "publish that file so images upload, or reference images via " +
            "pagedrop://asset/<id> / http(s) URLs.\n",
        );
      }
    }

    const body = {
      workspace_slug: opts.workspace,
      slug: opts.slug,
      title,
      content_type: contentType,
      content: finalContent,
      visibility: opts.visibility,
      message: opts.message ?? null,
      summary: opts.summary ?? null,
      source: "agent",
      force: Boolean(opts.force),
    };
    try {
      const res = await client.post<PublishResponse>("/projects.publish", body);
      process.stdout.write(
        `Published ${res.slug} v${res.version} (${res.visibility}, secrets: ${res.secret_scan_status}).\n` +
          `  latest:  ${res.latest_url}\n` +
          `  version: ${res.version_url}\n`,
      );
    } catch (err) {
      reportApiError(err);
    }
  });

program
  .command("versions")
  .description("List versions of a project")
  .requiredOption("-w, --workspace <slug>", "workspace slug")
  .requiredOption("-s, --slug <slug>", "project slug")
  .action(async (opts) => {
    try {
      const versions = await clientFromProfile(program.opts().profile).get<
        Array<{
          version_number: number;
          title: string;
          content_type: string;
          created_by_source: string;
          created_at: string;
          changelog: string | null;
        }>
      >(`/projects/${opts.workspace}/${opts.slug}/versions`);
      if (versions.length === 0) {
        process.stdout.write("(no versions)\n");
        return;
      }
      for (const v of versions) {
        process.stdout.write(
          `v${v.version_number}\t${v.content_type}\t${v.created_by_source}\t` +
            `${v.created_at}\t${v.title}${v.changelog ? ` — ${v.changelog}` : ""}\n`,
        );
      }
    } catch (err) {
      reportApiError(err);
    }
  });

interface ProjectListItem {
  id: string;
  workspace_id: string;
  slug: string;
  title: string;
  visibility: string;
  updated_at: string;
}

program
  .command("list")
  .description("List projects in a workspace (defaults to the token's workspace)")
  .option("--workspace-id <uuid>", "workspace id (required for user sessions)")
  .option("-q, --search <text>", "filter by title or slug")
  .option("--limit <n>", "max results (default 50)", (v) => parseInt(v, 10))
  .option("--offset <n>", "skip N results", (v) => parseInt(v, 10))
  .option("--json", "output raw JSON", false)
  .action(async (opts) => {
    const params = new URLSearchParams();
    if (opts.workspaceId) params.set("workspace_id", opts.workspaceId);
    if (opts.search) params.set("q", opts.search);
    if (opts.limit != null) params.set("limit", String(opts.limit));
    if (opts.offset != null) params.set("offset", String(opts.offset));
    const query = params.toString();
    try {
      const projects = await clientFromProfile(program.opts().profile).get<ProjectListItem[]>(
        `/projects${query ? `?${query}` : ""}`,
      );
      if (opts.json) {
        process.stdout.write(JSON.stringify(projects, null, 2) + "\n");
        return;
      }
      if (projects.length === 0) {
        process.stdout.write("(no projects)\n");
        return;
      }
      for (const p of projects) {
        process.stdout.write(`${p.slug}\t${p.visibility}\t${p.updated_at}\t${p.title}\n`);
      }
    } catch (err) {
      reportApiError(err);
    }
  });

program
  .command("info")
  .description("Show project metadata")
  .requiredOption("-w, --workspace <slug>", "workspace slug")
  .requiredOption("-s, --slug <slug>", "project slug")
  .action(async (opts) => {
    try {
      const project = await clientFromProfile(program.opts().profile).get(
        `/projects/${opts.workspace}/${opts.slug}`,
      );
      process.stdout.write(JSON.stringify(project, null, 2) + "\n");
    } catch (err) {
      reportApiError(err);
    }
  });

program
  .command("share")
  .description("Create a share link for a project")
  .requiredOption("-w, --workspace <slug>", "workspace slug")
  .requiredOption("-s, --slug <slug>", "project slug")
  .option("-a, --access-type <type>", "latest | fixed_version", "latest")
  .option("--version <n>", "version number (for fixed_version)", (v) => parseInt(v, 10))
  .option("--password <password>", "protect the link with a password")
  .option("--expires-at <iso>", "expiry timestamp (ISO 8601)")
  .option("--max-views <n>", "maximum number of views", (v) => parseInt(v, 10))
  .action(async (opts) => {
    const body = {
      access_type: opts.accessType,
      version: opts.version ?? null,
      password: opts.password ?? null,
      expires_at: opts.expiresAt ?? null,
      max_views: opts.maxViews ?? null,
    };
    try {
      const res = await clientFromProfile(program.opts().profile).post<{
        share_url: string;
        access_type: string;
        expires_at: string | null;
      }>(`/projects/${opts.workspace}/${opts.slug}/share-links`, body);
      process.stdout.write(
        `Share link created (${res.access_type}${res.expires_at ? `, expires ${res.expires_at}` : ""}):\n` +
          `  ${res.share_url}\n`,
      );
    } catch (err) {
      reportApiError(err);
    }
  });

program
  .command("pull")
  .description("Fetch a project's content and download its attached images locally")
  .requiredOption("-w, --workspace <slug>", "workspace slug")
  .requiredOption("-s, --slug <slug>", "project slug")
  .option("--version <n>", "version number (defaults to latest)", (v) => parseInt(v, 10))
  .option("-o, --out <dir>", "output directory", ".")
  .action(async (opts) => {
    const client = clientFromProfile(program.opts().profile);
    try {
      let versionNumber = opts.version as number | undefined;
      if (versionNumber === undefined) {
        const versions = await client.get<Array<{ version_number: number }>>(
          `/projects/${opts.workspace}/${opts.slug}/versions`,
        );
        if (versions.length === 0) fail("project has no versions");
        versionNumber = Math.max(...versions.map((v) => v.version_number));
      }
      const ver = await client.get<{
        source_content: string;
        content_type: string;
      }>(`/projects/${opts.workspace}/${opts.slug}/versions/${versionNumber}`);

      const outDir = resolve(opts.out);
      const assetsDir = join(outDir, "assets");
      let content = ver.source_content;
      const ids = extractAssetIds(content);
      if (ids.length > 0) mkdirSync(assetsDir, { recursive: true });
      for (const id of ids) {
        const { data, contentType } = await client.getBytes(`/assets/${id}`);
        const ext = EXT_BY_MIME[contentType] ?? "bin";
        const rel = join("assets", `${id}.${ext}`);
        writeFileSync(join(outDir, rel), data);
        content = replaceRef(content, `pagedrop://asset/${id}`, rel);
      }

      mkdirSync(outDir, { recursive: true });
      const ext = ver.content_type === "markdown" ? "md" : "html";
      const outFile = join(outDir, `${opts.slug}.${ext}`);
      writeFileSync(outFile, content);
      process.stdout.write(
        `Pulled ${opts.slug} v${versionNumber} → ${outFile}` +
          (ids.length ? ` (+${ids.length} image(s) in ${assetsDir})` : "") +
          "\n",
      );
    } catch (err) {
      reportApiError(err);
    }
  });

interface ReadPage {
  workspace_slug?: string;
  project_slug?: string;
  title: string;
  visibility?: string;
  content_type: string;
  source_content: string;
  version_number: number;
  is_latest?: boolean;
  summary?: string | null;
  changelog?: string | null;
  updated_at?: string;
}

type ReadTarget =
  | { kind: "share"; token: string; baseUrl?: string }
  | { kind: "version"; workspace: string; slug: string; version?: number; baseUrl?: string };

/** Resolve a positional target (share URL/token or page URL) plus -w/-s flags into a read target. */
function parseReadTarget(
  target: string | undefined,
  opts: { workspace?: string; slug?: string; version?: number },
): ReadTarget {
  const flagVersion = typeof opts.version === "number" && !Number.isNaN(opts.version)
    ? opts.version
    : undefined;

  if (target && /^https?:\/\//i.test(target)) {
    let u: URL;
    try {
      u = new URL(target);
    } catch {
      fail(`invalid URL: ${target}`);
    }
    const baseUrl = u.origin;
    const parts = u.pathname.split("/").filter(Boolean);
    const shareIdx = parts.indexOf("share");
    if (shareIdx !== -1 && parts[shareIdx + 1]) {
      return { kind: "share", token: parts[shareIdx + 1], baseUrl };
    }
    // /p/<ws>/<slug>[/v/<n>]  or  /manage/<ws>/<slug>
    const anchor = parts.findIndex((p) => p === "p" || p === "manage");
    if (anchor !== -1 && parts[anchor + 1] && parts[anchor + 2]) {
      let version = flagVersion;
      const vIdx = parts.indexOf("v", anchor + 2);
      if (vIdx !== -1 && parts[vIdx + 1]) {
        const n = parseInt(parts[vIdx + 1], 10);
        if (!Number.isNaN(n)) version = n;
      }
      return { kind: "version", workspace: parts[anchor + 1], slug: parts[anchor + 2], version, baseUrl };
    }
    fail(`unrecognized PageDrop URL: ${target}`);
  }

  if (target && target.startsWith(SHARE_PREFIX)) {
    return { kind: "share", token: target };
  }
  if (opts.workspace && opts.slug) {
    return { kind: "version", workspace: opts.workspace, slug: opts.slug, version: flagVersion };
  }
  if (target) {
    // A bare, non-URL token: treat as an (opaque) share token.
    return { kind: "share", token: target };
  }
  fail("provide a share URL/token, a page URL, or -w <ws> -s <slug>");
}

/** Build a client for a read: reuse the profile, but tolerate a missing profile for share links. */
function readClient(target: ReadTarget, profileName?: string): ApiClient {
  try {
    const { profile } = resolveProfile(profileName);
    return new ApiClient(target.baseUrl ?? profile.baseUrl, profile.token);
  } catch (err) {
    if (target.kind === "share") {
      return new ApiClient(target.baseUrl ?? DEFAULT_URL, "");
    }
    throw err;
  }
}

program
  .command("read")
  .description(
    "Read a page as structured data — from a share URL/token, a page URL (/p/ or /manage/), " +
      "or -w/-s (+ --version). Prints JSON to stdout by default; use --content for raw source, " +
      "-o to download files like pull.",
  )
  .argument("[target]", "share URL/token, page URL, or omit and use -w/-s")
  .option("-w, --workspace <slug>", "workspace slug (when no URL/token is given)")
  .option("-s, --slug <slug>", "project slug (when no URL/token is given)")
  .option("--version <n>", "version number (defaults to latest)", (v) => parseInt(v, 10))
  .option("--password <password>", "password for a protected share link")
  .option("--content", "print only the raw source content (not full JSON)", false)
  .option("-o, --out <dir>", "download to files (like pull) instead of printing")
  .action(async (target, opts) => {
    const t = parseReadTarget(target, opts);
    const client = readClient(t, program.opts().profile);
    try {
      let page: ReadPage;
      let resolvedVersion: number | undefined = t.kind === "version" ? t.version : undefined;

      if (t.kind === "share") {
        try {
          page = await client.get<ReadPage>(`/public/share/${t.token}`);
        } catch (err) {
          if (err instanceof ApiError && err.status === 401 && opts.password) {
            page = await client.post<ReadPage>(`/public/share/${t.token}/verify-password`, {
              password: opts.password,
            });
          } else if (err instanceof ApiError && err.status === 401) {
            fail("this share link is password-protected; pass --password <pw>");
          } else {
            throw err;
          }
        }
      } else {
        if (resolvedVersion === undefined) {
          const versions = await client.get<Array<{ version_number: number }>>(
            `/projects/${t.workspace}/${t.slug}/versions`,
          );
          if (versions.length === 0) fail("project has no versions");
          resolvedVersion = Math.max(...versions.map((v) => v.version_number));
        }
        page = await client.get<ReadPage>(
          `/projects/${t.workspace}/${t.slug}/versions/${resolvedVersion}`,
        );
      }

      if (opts.out) {
        const slug = t.kind === "version" ? t.slug : page.project_slug ?? "page";
        const outDir = resolve(opts.out);
        const assetsDir = join(outDir, "assets");
        let content = page.source_content;
        const ids = extractAssetIds(content);
        if (ids.length > 0) mkdirSync(assetsDir, { recursive: true });
        for (const id of ids) {
          // Share reads fetch via the public asset endpoint, carrying the share
          // token so private-page images resolve once the backend honors it.
          const path =
            t.kind === "share"
              ? `/public/assets/${id}?share_token=${encodeURIComponent(t.token)}`
              : `/assets/${id}`;
          const { data, contentType } = await client.getBytes(path);
          const ext = EXT_BY_MIME[contentType] ?? "bin";
          const rel = join("assets", `${id}.${ext}`);
          writeFileSync(join(outDir, rel), data);
          content = replaceRef(content, `pagedrop://asset/${id}`, rel);
        }
        mkdirSync(outDir, { recursive: true });
        const ext = page.content_type === "markdown" ? "md" : "html";
        const outFile = join(outDir, `${slug}.${ext}`);
        writeFileSync(outFile, content);
        process.stdout.write(
          `Read ${slug} v${page.version_number ?? resolvedVersion} → ${outFile}` +
            (ids.length ? ` (+${ids.length} image(s) in ${assetsDir})` : "") +
            "\n",
        );
        return;
      }

      if (opts.content) {
        process.stdout.write(page.source_content);
        if (!page.source_content.endsWith("\n")) process.stdout.write("\n");
        return;
      }
      process.stdout.write(JSON.stringify(page, null, 2) + "\n");
    } catch (err) {
      reportApiError(err);
    }
  });

const workspace = program
  .command("workspace")
  .description("Inspect workspaces available to the current credential");

workspace
  .command("list")
  .description("List workspaces (a token sees only the one it is bound to)")
  .option("--json", "output raw JSON", false)
  .action(async (opts) => {
    try {
      const list = await clientFromProfile(program.opts().profile).get<
        Array<{ id: string; slug: string; name: string; type: string; role: string }>
      >("/workspaces");
      if (opts.json) {
        process.stdout.write(JSON.stringify(list, null, 2) + "\n");
        return;
      }
      if (list.length === 0) {
        process.stdout.write("(no workspaces)\n");
        return;
      }
      for (const w of list) {
        process.stdout.write(`${w.slug}\t${w.type}\t${w.role || "-"}\t${w.name}\t${w.id}\n`);
      }
    } catch (err) {
      reportApiError(err);
    }
  });

const comments = program
  .command("comments")
  .description("Read and manage document comments");

comments
  .command("list")
  .description("List comments on a project (agent-ready with --json)")
  .requiredOption("-w, --workspace <slug>", "workspace slug")
  .requiredOption("-s, --slug <slug>", "project slug")
  .option("--status <status>", "filter by status: open | resolved")
  .option("--json", "output raw JSON", false)
  .action(async (opts) => {
    try {
      const q = opts.status ? `?status=${encodeURIComponent(opts.status)}` : "";
      const list = await clientFromProfile(program.opts().profile).get<CommentResponse[]>(
        `/projects/${opts.workspace}/${opts.slug}/comments${q}`,
      );
      if (opts.json) {
        process.stdout.write(JSON.stringify(list, null, 2) + "\n");
        return;
      }
      if (list.length === 0) {
        process.stdout.write("(no comments)\n");
        return;
      }
      for (const c of list) {
        const kind = c.thread_root_id ? "  ↳ reply" : `[${c.status}]`;
        const quote = c.anchor_quote ? ` on “${c.anchor_quote}”` : "";
        process.stdout.write(
          `${kind} ${c.id}\t${c.author_display ?? "?"}${quote}\n    ${c.body}\n`,
        );
      }
    } catch (err) {
      reportApiError(err);
    }
  });

comments
  .command("reply")
  .description("Reply to a comment thread")
  .argument("<comment_id>", "the root comment id to reply to")
  .argument("<body>", "reply text")
  .requiredOption("-w, --workspace <slug>", "workspace slug")
  .requiredOption("-s, --slug <slug>", "project slug")
  .action(async (commentId, body, opts) => {
    try {
      const res = await clientFromProfile(program.opts().profile).post<CommentResponse>(
        `/projects/${opts.workspace}/${opts.slug}/comments`,
        { body, thread_root_id: commentId },
      );
      process.stdout.write(`Replied (${res.id}).\n`);
    } catch (err) {
      reportApiError(err);
    }
  });

for (const verb of ["resolve", "reopen"] as const) {
  comments
    .command(verb)
    .description(`Mark a comment thread as ${verb === "resolve" ? "resolved" : "open"}`)
    .argument("<comment_id>", "the root comment id")
    .action(async (commentId) => {
      try {
        const res = await clientFromProfile(program.opts().profile).post<CommentResponse>(
          `/comments/${commentId}/${verb}`,
        );
        process.stdout.write(`Comment ${res.id} is now ${res.status}.\n`);
      } catch (err) {
        reportApiError(err);
      }
    });
}

program.parseAsync(process.argv).catch((err) => reportApiError(err));

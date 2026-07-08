#!/usr/bin/env node
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { basename, dirname, extname, join, resolve } from "node:path";

import { Command } from "commander";

import { ApiClient, ApiError } from "./api.js";
import { resolveProfile, upsertProfile, configPath, type Profile } from "./config.js";
import {
  EXT_BY_MIME,
  extractAssetIds,
  extractLocalImageRefs,
  mimeForPath,
  replaceRef,
} from "./media.js";

const DEFAULT_URL = "https://pagedrop.justinhuang.top";

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
  .description("Store an API token and verify it against the server")
  .requiredOption("-t, --token <token>", "PageDrop API token (pd_live_...)")
  .option("-u, --url <url>", "server base URL", DEFAULT_URL)
  .option("-n, --name <name>", "profile name", "default")
  .action(async (opts) => {
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

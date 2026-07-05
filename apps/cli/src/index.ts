#!/usr/bin/env node
import { readFileSync } from "node:fs";
import { basename, extname } from "node:path";

import { Command } from "commander";

import { ApiClient, ApiError } from "./api.js";
import { resolveProfile, upsertProfile, configPath, type Profile } from "./config.js";

const DEFAULT_URL = "https://pagedrop.justinhuang.top";

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
  .option("-v, --visibility <visibility>", "public | unlisted | private", "unlisted")
  .option("-m, --message <message>", "changelog message for this version")
  .option("--summary <summary>", "short summary")
  .option("--force", "publish even if secrets are detected", false)
  .action(async (file, opts) => {
    const content = readInput(file);
    const contentType = opts.contentType ?? (file ? contentTypeFromPath(file) : "markdown");
    const title = opts.title ?? (file ? basename(file, extname(file)) : opts.slug);
    const body = {
      workspace_slug: opts.workspace,
      slug: opts.slug,
      title,
      content_type: contentType,
      content,
      visibility: opts.visibility,
      message: opts.message ?? null,
      summary: opts.summary ?? null,
      source: "agent",
      force: Boolean(opts.force),
    };
    try {
      const res = await clientFromProfile(program.opts().profile).post<PublishResponse>(
        "/projects.publish",
        body,
      );
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

program.parseAsync(process.argv).catch((err) => reportApiError(err));

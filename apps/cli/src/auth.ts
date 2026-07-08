import { spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import { createInterface } from "node:readline/promises";

import { ApiClient } from "./api.js";
import { configPath, upsertProfile, type Profile } from "./config.js";

/** Scopes granted to a CLI-minted token: enough for the full publish workflow. */
export const DEFAULT_TOKEN_SCOPES = [
  "versions:write",
  "versions:read",
  "projects:read",
  "assets:write",
  "share_links:create",
  "comments:read",
  "comments:write",
];

/** Public (non-secret) client_id of the PageDrop GitHub OAuth App, with Device Flow enabled. */
export const GITHUB_CLIENT_ID =
  process.env.PAGEDROP_GITHUB_CLIENT_ID ?? "REPLACE_WITH_GITHUB_CLIENT_ID";

interface WorkspaceInfo {
  id: string;
  slug: string;
  type: string;
  role: string;
  name: string;
}

interface TokenCreateResponse {
  token: string;
  token_prefix: string;
  token_info: { name: string; scopes: string[] };
}

export function isTty(): boolean {
  return process.stdin.isTTY === true;
}

export async function prompt(question: string): Promise<string> {
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  try {
    return (await rl.question(question)).trim();
  } finally {
    rl.close();
  }
}

/** Prompt for a secret, muting the echoed characters. */
export async function promptHidden(question: string): Promise<string> {
  const rl = createInterface({ input: process.stdin, output: process.stdout, terminal: true });
  let muted = false;
  const rlAny = rl as unknown as { _writeToOutput: (s: string) => void };
  const origWrite = rlAny._writeToOutput.bind(rl);
  rlAny._writeToOutput = (s: string) => {
    if (muted) return;
    origWrite(s);
  };
  const answer = rl.question(question);
  muted = true;
  try {
    return (await answer).trim();
  } finally {
    rl.close();
    process.stdout.write("\n");
  }
}

/** Resolve a required value: flag wins; else prompt on a TTY; else fail with guidance. */
export async function resolveValue(
  flagValue: string | undefined,
  promptText: string,
  missingHint: string,
  hidden = false,
): Promise<string> {
  if (flagValue) return flagValue;
  if (!isTty()) throw new Error(missingHint);
  const value = hidden ? await promptHidden(promptText) : await prompt(promptText);
  if (!value) throw new Error(missingHint);
  return value;
}

export function randomPassword(): string {
  return randomBytes(18).toString("base64url");
}

/**
 * Given a client that already holds a session cookie, pick a workspace, mint a
 * scoped API token, store it in the profile, and print a ready-to-publish message.
 */
export async function mintTokenAndStore(
  client: ApiClient,
  opts: { baseUrl: string; workspaceSlug?: string; tokenName: string; profileName: string },
): Promise<void> {
  const workspaces = await client.get<WorkspaceInfo[]>("/workspaces");
  let slug = opts.workspaceSlug;
  if (!slug) {
    if (workspaces.length === 0) {
      throw new Error("no workspace found for this account");
    } else if (workspaces.length === 1) {
      slug = workspaces[0].slug;
    } else {
      const personal = workspaces.find((w) => w.type === "personal");
      if (isTty()) {
        process.stdout.write("Multiple workspaces:\n");
        workspaces.forEach((w, i) => process.stdout.write(`  ${i + 1}) ${w.slug} (${w.type})\n`));
        const pick = await prompt(`Select workspace [1-${workspaces.length}]: `);
        const idx = Number(pick) - 1;
        slug = workspaces[idx]?.slug;
        if (!slug) throw new Error("invalid selection");
      } else if (personal) {
        slug = personal.slug;
      } else {
        throw new Error(
          `multiple workspaces; pass --workspace <slug>: ${workspaces.map((w) => w.slug).join(", ")}`,
        );
      }
    }
  }

  const res = await client.post<TokenCreateResponse>("/tokens", {
    workspace_slug: slug,
    name: opts.tokenName,
    scopes: DEFAULT_TOKEN_SCOPES,
  });

  const profile: Profile = { baseUrl: opts.baseUrl, token: res.token, workspace: slug };
  upsertProfile(opts.profileName, profile);

  process.stdout.write(
    `Created token "${res.token_info.name}" in workspace "${slug}" ` +
      `(scopes: ${res.token_info.scopes.join(", ")}).\n` +
      `Saved to profile "${opts.profileName}" at ${configPath()}.\n` +
      "Ready — try `pagedrop publish <file> -w " +
      `${slug} -s <slug>\`.\n`,
  );
}

// ---------------------------------------------------------------------------
// GitHub OAuth device flow (runs against github.com; only a public client_id)
// ---------------------------------------------------------------------------

interface DeviceCodeResponse {
  device_code: string;
  user_code: string;
  verification_uri: string;
  expires_in: number;
  interval: number;
  error?: string;
  error_description?: string;
}

interface AccessTokenResponse {
  access_token?: string;
  error?: string;
  error_description?: string;
  interval?: number;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

async function githubForm<T>(url: string, params: Record<string, string>): Promise<T> {
  const resp = await fetch(url, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams(params).toString(),
  });
  return (await resp.json()) as T;
}

function tryOpenBrowser(url: string): void {
  try {
    const cmd =
      process.platform === "darwin" ? "open" : process.platform === "win32" ? "start" : "xdg-open";
    spawn(cmd, [url], { stdio: "ignore", detached: true }).unref();
  } catch {
    /* best-effort only */
  }
}

/** Run the GitHub device flow and return the user's GitHub access token. */
export async function githubDeviceFlow(clientId: string, openBrowser: boolean): Promise<string> {
  if (clientId === "REPLACE_WITH_GITHUB_CLIENT_ID") {
    throw new Error(
      "no GitHub client_id configured; pass --client-id <id> or set PAGEDROP_GITHUB_CLIENT_ID",
    );
  }

  const dc = await githubForm<DeviceCodeResponse>("https://github.com/login/device/code", {
    client_id: clientId,
    scope: "read:user user:email",
  });
  if (dc.error || !dc.device_code) {
    throw new Error(`GitHub: ${dc.error_description ?? dc.error ?? "device code request failed"}`);
  }

  process.stdout.write(
    `\nTo authorize PageDrop, open:\n  ${dc.verification_uri}\n` +
      `and enter the code: ${dc.user_code}\n\nWaiting for authorization...\n`,
  );
  if (openBrowser) tryOpenBrowser(dc.verification_uri);

  let interval = dc.interval || 5;
  const deadline = Date.now() + (dc.expires_in || 900) * 1000;
  while (Date.now() < deadline) {
    await sleep(interval * 1000);
    const tok = await githubForm<AccessTokenResponse>(
      "https://github.com/login/oauth/access_token",
      {
        client_id: clientId,
        device_code: dc.device_code,
        grant_type: "urn:ietf:params:oauth:grant-type:device_code",
      },
    );
    if (tok.access_token) return tok.access_token;
    switch (tok.error) {
      case "authorization_pending":
        break;
      case "slow_down":
        interval = tok.interval ?? interval + 5;
        break;
      case "expired_token":
        throw new Error("device code expired; run `pagedrop auth github` again");
      case "access_denied":
        throw new Error("authorization was denied");
      default:
        throw new Error(`GitHub: ${tok.error_description ?? tok.error ?? "unknown error"}`);
    }
  }
  throw new Error("timed out waiting for GitHub authorization");
}

import { chmodSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";

export interface Profile {
  baseUrl: string;
  token: string;
  workspace?: string;
}

export interface CliConfig {
  current: string;
  profiles: Record<string, Profile>;
}

const CONFIG_DIR = process.env.PAGEDROP_HOME ?? join(homedir(), ".pagedrop");
const CONFIG_PATH = join(CONFIG_DIR, "config.json");

const EMPTY: CliConfig = { current: "default", profiles: {} };

export function configPath(): string {
  return CONFIG_PATH;
}

export function loadConfig(): CliConfig {
  try {
    const raw = readFileSync(CONFIG_PATH, "utf8");
    const parsed = JSON.parse(raw) as Partial<CliConfig>;
    return {
      current: parsed.current ?? "default",
      profiles: parsed.profiles ?? {},
    };
  } catch {
    return { ...EMPTY, profiles: {} };
  }
}

export function saveConfig(config: CliConfig): void {
  mkdirSync(dirname(CONFIG_PATH), { recursive: true, mode: 0o700 });
  writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2), { mode: 0o600 });
  // Ensure permissions even if the file already existed with a looser mode.
  chmodSync(CONFIG_PATH, 0o600);
}

export function resolveProfile(name?: string): { name: string; profile: Profile } {
  const config = loadConfig();
  const profileName = name ?? process.env.PAGEDROP_PROFILE ?? config.current;
  const profile = config.profiles[profileName];

  // Environment variables always win, allowing token-less CI usage.
  const envBase = process.env.PAGEDROP_URL;
  const envToken = process.env.PAGEDROP_TOKEN;
  if (envToken || envBase) {
    return {
      name: profileName,
      profile: {
        baseUrl: envBase ?? profile?.baseUrl ?? "https://pagedrop.justinhuang.top",
        token: envToken ?? profile?.token ?? "",
        workspace: process.env.PAGEDROP_WORKSPACE ?? profile?.workspace,
      },
    };
  }

  if (!profile) {
    throw new Error(
      `No credentials for profile "${profileName}". Run \`pagedrop login\` first.`,
    );
  }
  return { name: profileName, profile };
}

export function upsertProfile(name: string, profile: Profile, makeCurrent = true): void {
  const config = loadConfig();
  config.profiles[name] = profile;
  if (makeCurrent) config.current = name;
  saveConfig(config);
}

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { tokenApi } from "@/api";
import { ApiRequestError } from "@/api/client";
import type { ApiToken } from "@/api/types";
import { useWorkspaceStore } from "@/stores/workspace";

const ws = useWorkspaceStore();
const current = computed(() => ws.current());

const ALL_SCOPES = [
  "projects:read",
  "projects:write",
  "versions:read",
  "versions:write",
  "assets:write",
  "comments:read",
  "comments:write",
  "share_links:create",
  "tokens:read",
];

const tokens = ref<ApiToken[]>([]);
const loading = ref(false);
const error = ref("");

const name = ref("");
const scopes = ref<string[]>(["versions:write"]);
const allowlist = ref("");
const expiresAt = ref("");
const creating = ref(false);
const createdPlaintext = ref("");

async function load() {
  if (!current.value) return;
  loading.value = true;
  error.value = "";
  try {
    tokens.value = await tokenApi.list(current.value.id);
  } catch (e) {
    error.value =
      e instanceof ApiRequestError && e.status === 403
        ? "You need admin access to manage tokens."
        : "Failed to load tokens.";
  } finally {
    loading.value = false;
  }
}

async function create() {
  if (!current.value) return;
  creating.value = true;
  error.value = "";
  createdPlaintext.value = "";
  try {
    const list = allowlist.value
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const res = await tokenApi.create({
      workspace_slug: current.value.slug,
      name: name.value.trim(),
      scopes: scopes.value,
      project_allowlist: list.length ? list : null,
      expires_at: expiresAt.value ? new Date(expiresAt.value).toISOString() : null,
    });
    createdPlaintext.value = res.token;
    name.value = "";
    allowlist.value = "";
    await load();
  } catch (e) {
    error.value = e instanceof ApiRequestError ? String(e.detail) : "Create failed.";
  } finally {
    creating.value = false;
  }
}

async function revoke(id: string) {
  await tokenApi.revoke(id);
  await load();
}

function copy(text: string) {
  navigator.clipboard?.writeText(text);
}

function toggleScope(s: string) {
  const i = scopes.value.indexOf(s);
  if (i >= 0) scopes.value.splice(i, 1);
  else scopes.value.push(s);
}

function selectAllScopes() {
  scopes.value = [...ALL_SCOPES];
}

function clearScopes() {
  scopes.value = [];
}

watch(() => current.value?.id, load, { immediate: true });
</script>

<template>
  <div class="container">
    <h1>API tokens</h1>
    <p class="muted">Scoped tokens for agents and the CLI in <strong>{{ current?.name }}</strong>.</p>

    <form class="card stack" @submit.prevent="create">
      <div class="field" style="margin: 0">
        <label>Name</label>
        <input v-model="name" class="input" placeholder="ci-bot" required />
      </div>
      <div class="field" style="margin: 0">
        <div class="scope-head">
          <label style="margin: 0">Scopes</label>
          <div class="scope-actions">
            <button type="button" class="btn btn-sm" @click="selectAllScopes">All</button>
            <button type="button" class="btn btn-sm" @click="clearScopes">None</button>
          </div>
        </div>
        <div class="scopes">
          <label v-for="s in ALL_SCOPES" :key="s" class="scope">
            <input
              type="checkbox"
              :checked="scopes.includes(s)"
              @change="toggleScope(s)"
            />
            <code>{{ s }}</code>
          </label>
        </div>
      </div>
      <div class="row wrap">
        <div class="field grow" style="margin: 0">
          <label>Project allowlist (comma-separated slugs, optional)</label>
          <input v-model="allowlist" class="input" placeholder="docs, changelog" />
        </div>
        <div class="field grow" style="margin: 0">
          <label>Expires (optional)</label>
          <input v-model="expiresAt" class="input" type="datetime-local" />
        </div>
      </div>
      <div>
        <button class="btn btn-primary" :disabled="creating || !scopes.length" type="submit">
          Create token
        </button>
      </div>
    </form>

    <div v-if="createdPlaintext" class="card created-token">
      <strong>Copy this token now — it will not be shown again.</strong>
      <div class="row wrap" style="margin-top: 0.5rem">
        <code class="grow">{{ createdPlaintext }}</code>
        <button class="btn btn-sm" @click="copy(createdPlaintext)">Copy</button>
      </div>
    </div>

    <p v-if="error" class="error" style="margin-top: 1rem">{{ error }}</p>
    <p v-if="loading" class="muted">Loading…</p>

    <div class="stack" style="margin-top: 1rem">
      <div v-for="t in tokens" :key="t.id" class="card row between wrap">
        <div>
          <strong>{{ t.name }}</strong>
          <span v-if="t.revoked_at" class="badge private">revoked</span>
          <div class="muted" style="font-size: 0.8rem; margin-top: 0.3rem">
            <code>{{ t.token_prefix }}…</code>
            · {{ t.scopes.join(", ") }}
            <span v-if="t.last_used_at"> · last used {{ new Date(t.last_used_at).toLocaleDateString() }}</span>
          </div>
        </div>
        <button v-if="!t.revoked_at" class="btn btn-danger btn-sm" @click="revoke(t.id)">
          Revoke
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scopes {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 1rem;
}
.scope-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.4rem;
}
.scope-actions {
  display: flex;
  gap: 0.35rem;
}
.scope {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}
.created-token {
  border-color: var(--warning);
  margin-top: 1rem;
}
.created-token code {
  overflow-wrap: anywhere;
}
</style>

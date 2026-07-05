<script setup lang="ts">
import { onMounted, ref } from "vue";
import { shareApi } from "@/api";
import { ApiRequestError } from "@/api/client";
import type { ShareLink } from "@/api/types";

const props = defineProps<{ ws: string; slug: string }>();

const links = ref<ShareLink[]>([]);
const loading = ref(false);
const error = ref("");

const accessType = ref("latest");
const version = ref<number | null>(null);
const password = ref("");
const expiresAt = ref("");
const maxViews = ref<number | null>(null);
const creating = ref(false);
const createdUrl = ref("");

async function load() {
  loading.value = true;
  error.value = "";
  try {
    links.value = await shareApi.list(props.ws, props.slug);
  } catch {
    error.value = "Failed to load share links.";
  } finally {
    loading.value = false;
  }
}

async function create() {
  creating.value = true;
  error.value = "";
  createdUrl.value = "";
  try {
    const res = await shareApi.create(props.ws, props.slug, {
      access_type: accessType.value,
      version: accessType.value === "fixed_version" ? version.value : null,
      password: password.value || null,
      expires_at: expiresAt.value ? new Date(expiresAt.value).toISOString() : null,
      max_views: maxViews.value,
    });
    createdUrl.value = res.share_url;
    password.value = "";
    await load();
  } catch (e) {
    error.value = e instanceof ApiRequestError ? String(e.detail) : "Create failed.";
  } finally {
    creating.value = false;
  }
}

async function revoke(id: string) {
  await shareApi.revoke(id);
  await load();
}

function copy(text: string) {
  navigator.clipboard?.writeText(text);
}

onMounted(load);
</script>

<template>
  <div class="stack">
    <form class="card stack" @submit.prevent="create">
      <strong>Create share link</strong>
      <div class="row wrap">
        <div class="field grow" style="margin: 0">
          <label>Access</label>
          <select v-model="accessType" class="select">
            <option value="latest">Always latest</option>
            <option value="fixed_version">Fixed version</option>
          </select>
        </div>
        <div v-if="accessType === 'fixed_version'" class="field grow" style="margin: 0">
          <label>Version #</label>
          <input v-model.number="version" class="input" type="number" min="1" />
        </div>
      </div>
      <div class="row wrap">
        <div class="field grow" style="margin: 0">
          <label>Password (optional)</label>
          <input v-model="password" class="input" type="text" />
        </div>
        <div class="field grow" style="margin: 0">
          <label>Expires (optional)</label>
          <input v-model="expiresAt" class="input" type="datetime-local" />
        </div>
        <div class="field grow" style="margin: 0">
          <label>Max views (optional)</label>
          <input v-model.number="maxViews" class="input" type="number" min="1" />
        </div>
      </div>
      <div>
        <button class="btn btn-primary" :disabled="creating" type="submit">Create link</button>
      </div>
      <div v-if="createdUrl" class="row wrap created">
        <code class="grow">{{ createdUrl }}</code>
        <button class="btn btn-sm" type="button" @click="copy(createdUrl)">Copy</button>
      </div>
    </form>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="loading" class="muted">Loading…</p>

    <div v-for="link in links" :key="link.id" class="card row between wrap">
      <div>
        <div>
          <span class="badge">{{ link.access_type }}</span>
          <span v-if="link.has_password" class="badge">password</span>
          <span v-if="link.revoked_at" class="badge private">revoked</span>
        </div>
        <div class="muted" style="font-size: 0.82rem; margin-top: 0.3rem">
          {{ link.view_count }} views<span v-if="link.max_views"> / {{ link.max_views }}</span>
          <span v-if="link.expires_at"> · expires {{ new Date(link.expires_at).toLocaleString() }}</span>
        </div>
      </div>
      <button v-if="!link.revoked_at" class="btn btn-danger btn-sm" @click="revoke(link.id)">
        Revoke
      </button>
    </div>
  </div>
</template>

<style scoped>
.created code {
  overflow-wrap: anywhere;
}
</style>

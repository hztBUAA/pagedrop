<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";
import { assetApi, projectApi } from "@/api";
import { ApiRequestError } from "@/api/client";
import type { SecretFinding } from "@/api/types";
import { useWorkspaceStore } from "@/stores/workspace";

const ws = useWorkspaceStore();
const router = useRouter();
const current = computed(() => ws.current());

const slug = ref("");
const title = ref("");
const contentType = ref("markdown");
const visibility = ref("private");
const content = ref("");
const message = ref("");
const force = ref(false);

const busy = ref(false);
const error = ref("");
const findings = ref<SecretFinding[]>([]);

const fileInput = ref<HTMLInputElement | null>(null);
const uploading = ref(false);

const contentTypes = ["markdown", "safe_html", "sandbox_html"];
const visibilities = ["public", "unlisted", "private"];

function insertRef(assetRef: string, name: string) {
  const snippet =
    contentType.value === "markdown"
      ? `![${name}](${assetRef})`
      : `<img src="${assetRef}" alt="${name}" />`;
  content.value += (content.value && !content.value.endsWith("\n") ? "\n" : "") + snippet + "\n";
}

async function onFilePicked(e: Event) {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file || !current.value) return;
  uploading.value = true;
  error.value = "";
  try {
    const asset = await assetApi.upload(
      current.value.slug,
      slug.value.trim() || null,
      file,
    );
    insertRef(asset.ref, file.name);
  } catch (e) {
    error.value =
      e instanceof ApiRequestError ? `Image upload failed: ${String(e.detail)}` : "Image upload failed.";
  } finally {
    uploading.value = false;
  }
}

async function publish() {
  if (!current.value) {
    error.value = "No workspace selected.";
    return;
  }
  error.value = "";
  findings.value = [];
  busy.value = true;
  try {
    const res = await projectApi.publish({
      workspace_slug: current.value.slug,
      slug: slug.value.trim(),
      title: title.value.trim(),
      content_type: contentType.value,
      content: content.value,
      visibility: visibility.value,
      message: message.value || null,
      source: "web",
      force: force.value,
    });
    router.push({
      name: "project-manage",
      params: { ws: current.value.slug, slug: res.slug },
    });
  } catch (e) {
    if (e instanceof ApiRequestError) {
      const detail = e.detail as any;
      if (e.status === 400 && detail?.error === "secret_detected") {
        findings.value = detail.findings ?? [];
        error.value = detail.message ?? "Potential secrets detected.";
      } else if (e.status === 429) {
        error.value = "Rate limited. Slow down and retry.";
      } else if (e.status === 403) {
        error.value = "You do not have permission to publish here.";
      } else {
        error.value = typeof detail === "string" ? detail : "Publish failed.";
      }
    } else {
      error.value = "Publish failed.";
    }
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div class="container">
    <h1>New page</h1>
    <form class="stack" @submit.prevent="publish">
      <div class="row wrap">
        <div class="field grow" style="margin: 0">
          <label>Title</label>
          <input v-model="title" class="input" required />
        </div>
        <div class="field grow" style="margin: 0">
          <label>Slug</label>
          <input v-model="slug" class="input" placeholder="my-page" required />
        </div>
      </div>

      <div class="row wrap">
        <div class="field grow" style="margin: 0">
          <label>Content type</label>
          <select v-model="contentType" class="select">
            <option v-for="c in contentTypes" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
        <div class="field grow" style="margin: 0">
          <label>Visibility</label>
          <select v-model="visibility" class="select">
            <option v-for="v in visibilities" :key="v" :value="v">{{ v }}</option>
          </select>
        </div>
      </div>

      <div class="field" style="margin: 0">
        <div class="row between" style="align-items: center">
          <label style="margin: 0">Content</label>
          <button type="button" class="btn btn-sm" :disabled="uploading" @click="fileInput?.click()">
            {{ uploading ? "Uploading…" : "Insert image" }}
          </button>
          <input
            ref="fileInput"
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            hidden
            @change="onFilePicked"
          />
        </div>
        <textarea v-model="content" class="textarea" required />
      </div>

      <div class="field" style="margin: 0">
        <label>Changelog message (optional)</label>
        <input v-model="message" class="input" placeholder="Initial version" />
      </div>

      <div v-if="findings.length" class="card secret-box">
        <strong>Blocked: potential secrets detected.</strong>
        <ul>
          <li v-for="(f, i) in findings" :key="i">
            <code>{{ f.rule }}</code> (line {{ f.line }}): {{ f.preview }}
          </li>
        </ul>
        <label class="row" style="gap: 0.5rem">
          <input v-model="force" type="checkbox" />
          I understand — publish anyway
        </label>
      </div>

      <p v-if="error && !findings.length" class="error">{{ error }}</p>

      <div class="row">
        <button class="btn btn-primary" :disabled="busy" type="submit">
          {{ busy ? "Publishing…" : "Publish" }}
        </button>
        <router-link :to="{ name: 'dashboard' }" class="btn">Cancel</router-link>
      </div>
    </form>
  </div>
</template>

<style scoped>
.secret-box {
  border-color: var(--danger);
}
.secret-box ul {
  margin: 0.5rem 0;
  padding-left: 1.2rem;
}
</style>

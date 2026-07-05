<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { projectApi } from "@/api";
import { ApiRequestError } from "@/api/client";
import type { Project, Version, VersionSummary } from "@/api/types";
import PageRenderer from "@/components/PageRenderer.vue";
import ProjectSettings from "@/components/ProjectSettings.vue";
import ShareLinks from "@/components/ShareLinks.vue";

const route = useRoute();
const wsSlug = computed(() => route.params.ws as string);
const projectSlug = computed(() => route.params.slug as string);

type Tab = "view" | "history" | "settings" | "share";
const tab = ref<Tab>("view");

const project = ref<Project | null>(null);
const versions = ref<VersionSummary[]>([]);
const active = ref<Version | null>(null);
const loading = ref(true);
const error = ref("");

async function loadProject() {
  loading.value = true;
  error.value = "";
  try {
    project.value = await projectApi.get(wsSlug.value, projectSlug.value);
    versions.value = await projectApi.versions(wsSlug.value, projectSlug.value);
    const target = versions.value[0]?.version_number;
    if (target) await loadVersion(target);
  } catch (e) {
    if (e instanceof ApiRequestError && e.status === 403) error.value = "Access denied.";
    else if (e instanceof ApiRequestError && e.status === 404) error.value = "Not found.";
    else error.value = "Failed to load project.";
  } finally {
    loading.value = false;
  }
}

async function loadVersion(n: number) {
  active.value = await projectApi.version(wsSlug.value, projectSlug.value, n);
}

function viewVersion(n: number) {
  loadVersion(n);
  tab.value = "view";
}

const publicUrl = computed(() =>
  project.value ? `/p/${wsSlug.value}/${projectSlug.value}` : "",
);

watch([wsSlug, projectSlug], loadProject, { immediate: true });
</script>

<template>
  <div class="container">
    <p v-if="loading" class="muted">Loading…</p>
    <p v-else-if="error" class="error">{{ error }}</p>

    <template v-else-if="project">
      <div class="row between wrap head">
        <div>
          <h1 style="margin: 0 0 0.3rem">{{ project.title }}</h1>
          <div class="muted slug">
            <span class="badge" :class="project.visibility">{{ project.visibility }}</span>
            <router-link :to="publicUrl">{{ publicUrl }}</router-link>
          </div>
        </div>
      </div>

      <nav class="tabs">
        <button :class="{ on: tab === 'view' }" @click="tab = 'view'">View</button>
        <button :class="{ on: tab === 'history' }" @click="tab = 'history'">
          History ({{ versions.length }})
        </button>
        <button :class="{ on: tab === 'share' }" @click="tab = 'share'">Share</button>
        <button :class="{ on: tab === 'settings' }" @click="tab = 'settings'">Settings</button>
      </nav>

      <section v-show="tab === 'view'">
        <div v-if="active">
          <div class="muted version-meta">
            v{{ active.version_number }} · {{ active.content_type }} ·
            {{ new Date(active.created_at).toLocaleString() }}
            <span v-if="active.secret_scan_status !== 'clean'" class="badge unlisted">
              scan: {{ active.secret_scan_status }}
            </span>
          </div>
          <PageRenderer
            :content-type="active.content_type"
            :source-content="active.source_content"
            :rendered-html="active.rendered_html"
          />
        </div>
        <p v-else class="muted">No versions published yet.</p>
      </section>

      <section v-show="tab === 'history'" class="stack">
        <button
          v-for="v in versions"
          :key="v.id"
          class="card row between version-row"
          @click="viewVersion(v.version_number)"
        >
          <div>
            <strong>v{{ v.version_number }}</strong> — {{ v.title }}
            <div class="muted" style="font-size: 0.8rem">
              {{ v.created_by_source }} · {{ new Date(v.created_at).toLocaleString() }}
              <span v-if="v.changelog"> · {{ v.changelog }}</span>
            </div>
          </div>
        </button>
      </section>

      <section v-show="tab === 'share'">
        <ShareLinks :ws="wsSlug" :slug="projectSlug" />
      </section>

      <section v-show="tab === 'settings'">
        <ProjectSettings :ws="wsSlug" :project="project" @updated="project = $event" />
      </section>
    </template>
  </div>
</template>

<style scoped>
.head {
  margin-bottom: 1rem;
}
.slug {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
}
.tabs {
  display: flex;
  gap: 0.25rem;
  border-bottom: 1px solid var(--border);
  margin-bottom: 1rem;
  overflow-x: auto;
}
.tabs button {
  background: transparent;
  border: none;
  color: var(--text-dim);
  padding: 0.6rem 0.9rem;
  border-bottom: 2px solid transparent;
  white-space: nowrap;
}
.tabs button.on {
  color: var(--text);
  border-bottom-color: var(--accent);
}
.version-meta {
  font-size: 0.82rem;
  margin-bottom: 0.75rem;
}
.version-row {
  color: var(--text);
  width: 100%;
  text-align: left;
  cursor: pointer;
}
.version-row:hover {
  border-color: var(--accent);
}
</style>

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

// Mobile: collapse the slug/visibility line so the tabs + content sit higher.
const detailsOpen = ref(false);

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
      <header class="proj-head" :class="{ open: detailsOpen }">
        <div class="proj-bar">
          <h1 class="proj-title">{{ project.title }}</h1>
          <button
            type="button"
            class="proj-toggle"
            :aria-expanded="detailsOpen"
            aria-label="Toggle details"
            @click="detailsOpen = !detailsOpen"
          >
            <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
              <path
                d="M6 9l6 6 6-6"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
          </button>
        </div>
        <div class="proj-details muted">
          <span class="badge" :class="project.visibility">{{ project.visibility }}</span>
          <router-link :to="publicUrl">{{ publicUrl }}</router-link>
        </div>
      </header>

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
.proj-head {
  margin-bottom: 0.85rem;
}
.proj-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.proj-title {
  margin: 0;
  flex: 1;
  min-width: 0;
  font-size: 1.5rem;
  line-height: 1.3;
}
.proj-toggle {
  display: none;
  flex: none;
  width: 34px;
  height: 34px;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface-2);
  color: var(--text-dim);
  padding: 0;
  transition: transform 0.2s ease;
}
.proj-details {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  margin-top: 0.4rem;
  flex-wrap: wrap;
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
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem;
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

@media (max-width: 640px) {
  .proj-head {
    margin-bottom: 0.6rem;
  }
  .proj-title {
    font-size: 1.15rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .proj-toggle {
    display: inline-flex;
  }
  .proj-head.open .proj-toggle {
    transform: rotate(180deg);
  }
  .proj-details {
    display: none;
  }
  .proj-head.open .proj-details {
    display: flex;
  }
  .tabs {
    margin-bottom: 0.75rem;
  }
  .tabs button {
    padding: 0.5rem 0.7rem;
    font-size: 0.9rem;
  }
}
</style>

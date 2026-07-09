<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { projectApi } from "@/api";
import type { Project } from "@/api/types";
import { useWorkspaceStore } from "@/stores/workspace";

const PAGE_SIZE = 20;

const ws = useWorkspaceStore();
const projects = ref<Project[]>([]);
const folders = ref<string[]>([]);
const loading = ref(false);
const loadingMore = ref(false);
const error = ref("");
const showNewWs = ref(false);
const newWsName = ref("");
const search = ref("");
const offset = ref(0);
const hasMore = ref(false);
const selectedFolder = ref("");
const status = ref<"active" | "archived">("active");

const current = computed(() => ws.current());

// Split "ops/pagedrop" into clickable breadcrumb segments.
const breadcrumb = computed(() => {
  if (!selectedFolder.value) return [];
  const parts = selectedFolder.value.split("/");
  return parts.map((name, i) => ({ name, path: parts.slice(0, i + 1).join("/") }));
});

async function loadFolders() {
  if (!ws.currentId) {
    folders.value = [];
    return;
  }
  try {
    folders.value = await projectApi.folders(ws.currentId);
  } catch {
    folders.value = [];
  }
}

async function loadProjects(reset = true) {
  if (!ws.currentId) {
    projects.value = [];
    return;
  }
  if (reset) {
    offset.value = 0;
    loading.value = true;
  } else {
    loadingMore.value = true;
  }
  error.value = "";
  try {
    const batch = await projectApi.list(ws.currentId, {
      q: search.value.trim() || undefined,
      folder: selectedFolder.value || undefined,
      status: status.value,
      limit: PAGE_SIZE,
      offset: offset.value,
    });
    projects.value = reset ? batch : [...projects.value, ...batch];
    hasMore.value = batch.length === PAGE_SIZE;
    offset.value += batch.length;
  } catch {
    error.value = "Failed to load projects.";
  } finally {
    loading.value = false;
    loadingMore.value = false;
  }
}

function selectFolder(path: string) {
  selectedFolder.value = path;
}

async function createWorkspace() {
  if (!newWsName.value.trim()) return;
  await ws.create(newWsName.value.trim());
  newWsName.value = "";
  showNewWs.value = false;
}

// Debounce search so we don't fire a request per keystroke.
let searchTimer: ReturnType<typeof setTimeout> | null = null;
watch(search, () => {
  if (searchTimer) clearTimeout(searchTimer);
  searchTimer = setTimeout(() => loadProjects(true), 250);
});

watch([selectedFolder, status], () => loadProjects(true));

watch(
  () => ws.currentId,
  () => {
    selectedFolder.value = "";
    loadFolders();
    loadProjects(true);
  },
  { immediate: true },
);
</script>

<template>
  <div class="container">
    <div class="row between wrap" style="margin-bottom: 1rem">
      <h1 style="margin: 0">{{ current?.name ?? "Dashboard" }}</h1>
      <div class="row">
        <button class="btn btn-sm" @click="showNewWs = !showNewWs">New workspace</button>
        <router-link :to="{ name: 'new-page' }" class="btn btn-sm btn-primary">
          New page
        </router-link>
      </div>
    </div>

    <form v-if="showNewWs" class="card" style="margin-bottom: 1rem" @submit.prevent="createWorkspace">
      <div class="row">
        <input v-model="newWsName" class="input grow" placeholder="Workspace name" />
        <button class="btn btn-primary" type="submit">Create</button>
      </div>
    </form>

    <div class="row between wrap" style="margin-bottom: 1rem; gap: 0.5rem">
      <input
        v-model="search"
        class="input grow"
        type="search"
        placeholder="Search pages by title or slug…"
      />
      <div class="row" style="gap: 0.25rem">
        <button
          class="btn btn-sm"
          :class="{ 'btn-primary': status === 'active' }"
          @click="status = 'active'"
        >
          Active
        </button>
        <button
          class="btn btn-sm"
          :class="{ 'btn-primary': status === 'archived' }"
          @click="status = 'archived'"
        >
          Archived
        </button>
      </div>
    </div>

    <div class="layout">
      <aside v-if="folders.length" class="folders card">
        <button
          class="folder-item"
          :class="{ active: selectedFolder === '' }"
          @click="selectFolder('')"
        >
          All pages
        </button>
        <button
          v-for="f in folders"
          :key="f"
          class="folder-item"
          :class="{ active: selectedFolder === f }"
          :style="{ paddingLeft: `${0.6 + f.split('/').length * 0.6}rem` }"
          @click="selectFolder(f)"
        >
          {{ f.split("/").slice(-1)[0] }}
        </button>
      </aside>

      <div class="main">
        <nav v-if="breadcrumb.length" class="breadcrumb muted">
          <button class="crumb" @click="selectFolder('')">All</button>
          <template v-for="c in breadcrumb" :key="c.path">
            <span class="sep">/</span>
            <button class="crumb" @click="selectFolder(c.path)">{{ c.name }}</button>
          </template>
        </nav>

        <p v-if="loading" class="muted">Loading…</p>
        <p v-else-if="error" class="error">{{ error }}</p>
        <div v-else-if="!projects.length" class="card muted">
          <template v-if="search.trim()">No pages match “{{ search.trim() }}”.</template>
          <template v-else-if="status === 'archived'">No archived pages.</template>
          <template v-else-if="selectedFolder">No pages in this folder.</template>
          <template v-else>
            No pages yet.
            <router-link :to="{ name: 'new-page' }">Publish your first page.</router-link>
          </template>
        </div>

        <div v-else class="stack">
          <router-link
            v-for="p in projects"
            :key="p.id"
            class="card project-row row between"
            :to="{ name: 'project-manage', params: { ws: current?.slug, slug: p.slug } }"
          >
            <div>
              <div class="title">{{ p.title }}</div>
              <div class="muted slug">
                <span v-if="p.folder_path">{{ p.folder_path }}/ · </span
                >/{{ current?.slug }}/{{ p.slug }}
              </div>
            </div>
            <span class="badge" :class="p.visibility">{{ p.visibility }}</span>
          </router-link>

          <button
            v-if="hasMore"
            class="btn btn-sm"
            style="align-self: center"
            :disabled="loadingMore"
            @click="loadProjects(false)"
          >
            {{ loadingMore ? "Loading…" : "Load more" }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.layout {
  display: flex;
  gap: 1rem;
  align-items: flex-start;
}
.folders {
  flex: 0 0 200px;
  padding: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}
.folder-item {
  text-align: left;
  background: none;
  border: none;
  color: var(--text);
  padding: 0.35rem 0.6rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
}
.folder-item:hover {
  background: var(--surface-2, rgba(127, 127, 127, 0.1));
}
.folder-item.active {
  background: var(--accent);
  color: #fff;
}
.main {
  flex: 1 1 auto;
  min-width: 0;
}
.breadcrumb {
  margin-bottom: 0.75rem;
  font-size: 0.85rem;
}
.crumb {
  background: none;
  border: none;
  color: var(--accent);
  cursor: pointer;
  padding: 0;
  font: inherit;
}
.sep {
  margin: 0 0.3rem;
}
.project-row {
  color: var(--text);
}
.project-row:hover {
  border-color: var(--accent);
}
.title {
  font-weight: 600;
}
.slug {
  font-size: 0.82rem;
  margin-top: 0.15rem;
}
@media (max-width: 640px) {
  .layout {
    flex-direction: column;
  }
  .folders {
    flex-basis: auto;
    width: 100%;
    flex-direction: row;
    flex-wrap: wrap;
    overflow-x: auto;
  }
}
</style>

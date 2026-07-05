<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { projectApi } from "@/api";
import type { Project } from "@/api/types";
import { useWorkspaceStore } from "@/stores/workspace";

const ws = useWorkspaceStore();
const projects = ref<Project[]>([]);
const loading = ref(false);
const error = ref("");
const showNewWs = ref(false);
const newWsName = ref("");

const current = computed(() => ws.current());

async function loadProjects() {
  if (!ws.currentId) {
    projects.value = [];
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    projects.value = await projectApi.list(ws.currentId);
  } catch {
    error.value = "Failed to load projects.";
  } finally {
    loading.value = false;
  }
}

async function createWorkspace() {
  if (!newWsName.value.trim()) return;
  await ws.create(newWsName.value.trim());
  newWsName.value = "";
  showNewWs.value = false;
}

watch(() => ws.currentId, loadProjects, { immediate: true });
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

    <p v-if="loading" class="muted">Loading…</p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <div v-else-if="!projects.length" class="card muted">
      No pages yet. <router-link :to="{ name: 'new-page' }">Publish your first page.</router-link>
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
          <div class="muted slug">/{{ current?.slug }}/{{ p.slug }}</div>
        </div>
        <span class="badge" :class="p.visibility">{{ p.visibility }}</span>
      </router-link>
    </div>
  </div>
</template>

<style scoped>
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
</style>

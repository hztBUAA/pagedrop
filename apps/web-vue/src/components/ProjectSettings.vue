<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { projectApi } from "@/api";
import { ApiRequestError } from "@/api/client";
import type { Project } from "@/api/types";

const props = defineProps<{ ws: string; project: Project }>();
const emit = defineEmits<{ updated: [Project] }>();

const router = useRouter();
const title = ref(props.project.title);
const description = ref(props.project.description ?? "");
const visibility = ref(props.project.visibility);
const folderPath = ref(props.project.folder_path ?? "");
const status = ref(props.project.status);
const busy = ref(false);
const error = ref("");
const saved = ref(false);

const visibilities = ["public", "unlisted", "private"];

async function save() {
  busy.value = true;
  error.value = "";
  saved.value = false;
  try {
    const updated = await projectApi.updateSettings(props.ws, props.project.slug, {
      title: title.value,
      description: description.value,
      visibility: visibility.value,
      folder_path: folderPath.value.trim(),
    });
    emit("updated", updated);
    saved.value = true;
  } catch (e) {
    error.value = e instanceof ApiRequestError ? String(e.detail) : "Save failed.";
  } finally {
    busy.value = false;
  }
}

async function toggleArchive() {
  busy.value = true;
  error.value = "";
  try {
    const updated =
      status.value === "archived"
        ? await projectApi.unarchive(props.ws, props.project.slug)
        : await projectApi.archive(props.ws, props.project.slug);
    status.value = updated.status;
    emit("updated", updated);
  } catch (e) {
    error.value = e instanceof ApiRequestError ? String(e.detail) : "Action failed.";
  } finally {
    busy.value = false;
  }
}

async function remove() {
  if (!confirm("Delete this page? It will be hidden everywhere and can only be restored by support.")) {
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    await projectApi.del(props.ws, props.project.slug);
    router.push({ name: "dashboard" });
  } catch (e) {
    error.value = e instanceof ApiRequestError ? String(e.detail) : "Delete failed.";
    busy.value = false;
  }
}
</script>

<template>
  <form class="card stack" @submit.prevent="save">
    <div class="field" style="margin: 0">
      <label>Title</label>
      <input v-model="title" class="input" />
    </div>
    <div class="field" style="margin: 0">
      <label>Description</label>
      <input v-model="description" class="input" />
    </div>
    <div class="field" style="margin: 0">
      <label>Folder</label>
      <input v-model="folderPath" class="input" placeholder="e.g. ops/pagedrop (blank = root)" />
    </div>
    <div class="field" style="margin: 0">
      <label>Visibility</label>
      <select v-model="visibility" class="select">
        <option v-for="v in visibilities" :key="v" :value="v">{{ v }}</option>
      </select>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="saved" class="muted" style="color: var(--success)">Saved.</p>
    <div class="row between wrap">
      <button class="btn btn-primary" :disabled="busy" type="submit">Save settings</button>
      <div class="row" style="gap: 0.5rem">
        <button class="btn btn-sm" type="button" :disabled="busy" @click="toggleArchive">
          {{ status === "archived" ? "Unarchive" : "Archive" }}
        </button>
        <button class="btn btn-sm btn-danger" type="button" :disabled="busy" @click="remove">
          Delete
        </button>
      </div>
    </div>
  </form>
</template>

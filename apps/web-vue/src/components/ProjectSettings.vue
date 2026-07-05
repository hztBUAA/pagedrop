<script setup lang="ts">
import { ref } from "vue";
import { projectApi } from "@/api";
import { ApiRequestError } from "@/api/client";
import type { Project } from "@/api/types";

const props = defineProps<{ ws: string; project: Project }>();
const emit = defineEmits<{ updated: [Project] }>();

const title = ref(props.project.title);
const description = ref(props.project.description ?? "");
const visibility = ref(props.project.visibility);
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
    });
    emit("updated", updated);
    saved.value = true;
  } catch (e) {
    error.value = e instanceof ApiRequestError ? String(e.detail) : "Save failed.";
  } finally {
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
      <label>Visibility</label>
      <select v-model="visibility" class="select">
        <option v-for="v in visibilities" :key="v" :value="v">{{ v }}</option>
      </select>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="saved" class="muted" style="color: var(--success)">Saved.</p>
    <div>
      <button class="btn btn-primary" :disabled="busy" type="submit">Save settings</button>
    </div>
  </form>
</template>

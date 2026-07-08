<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { publicApi } from "@/api";
import { ApiRequestError } from "@/api/client";
import type { PublicPage } from "@/api/types";
import { useAuthStore } from "@/stores/auth";
import PageRenderer from "@/components/PageRenderer.vue";
import DocHeader from "@/components/DocHeader.vue";

const route = useRoute();
const auth = useAuthStore();

const wsSlug = computed(() => route.params.ws as string);
const projectSlug = computed(() => route.params.slug as string);
const version = computed(() =>
  route.params.version ? Number(route.params.version) : null,
);

const page = ref<PublicPage | null>(null);
const loading = ref(true);
const error = ref("");

function applyNoindex(noindex: boolean) {
  const id = "pd-robots";
  document.getElementById(id)?.remove();
  if (noindex) {
    const m = document.createElement("meta");
    m.id = id;
    m.name = "robots";
    m.content = "noindex, nofollow";
    document.head.appendChild(m);
  }
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    page.value = version.value
      ? await publicApi.version(wsSlug.value, projectSlug.value, version.value)
      : await publicApi.latest(wsSlug.value, projectSlug.value);
    applyNoindex(page.value.noindex);
  } catch (e) {
    if (e instanceof ApiRequestError && e.status === 404) error.value = "Page not found.";
    else error.value = "Unable to load page.";
  } finally {
    loading.value = false;
  }
}

const manageLink = computed(() => ({
  name: "project-manage",
  params: { ws: wsSlug.value, slug: projectSlug.value },
}));

onMounted(load);
watch([wsSlug, projectSlug, version], load);
</script>

<template>
  <div class="public-wrap">
    <p v-if="loading" class="muted container">Loading…</p>
    <div v-else-if="error" class="container">
      <div class="card">{{ error }}</div>
    </div>
    <article v-else-if="page" class="container reader">
      <DocHeader :title="page.title">
        <template #meta>
          <span class="badge" :class="page.visibility">{{ page.visibility }}</span>
          v{{ page.version_number }}
          <span v-if="!page.is_latest"> (older version)</span>
          · updated {{ new Date(page.updated_at).toLocaleString() }}
        </template>
        <template #actions>
          <router-link v-if="auth.user" :to="manageLink" class="btn btn-sm">Manage</router-link>
        </template>
      </DocHeader>
      <PageRenderer
        :content-type="page.content_type"
        :source-content="page.source_content"
        :rendered-html="page.rendered_html"
        :public-view="true"
      />
    </article>
  </div>
</template>

<style scoped>
.public-wrap {
  min-height: 100dvh;
}
.reader {
  max-width: 820px;
}
@media (max-width: 640px) {
  .reader {
    padding: 0 0.85rem 1.5rem;
  }
}
</style>

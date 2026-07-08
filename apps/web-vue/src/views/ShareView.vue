<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { publicApi } from "@/api";
import { ApiRequestError } from "@/api/client";
import type { PublicPage } from "@/api/types";
import PageRenderer from "@/components/PageRenderer.vue";
import DocHeader from "@/components/DocHeader.vue";

const route = useRoute();
const token = () => route.params.token as string;

const page = ref<PublicPage | null>(null);
const needsPassword = ref(false);
const password = ref("");
const error = ref("");
const loading = ref(true);
const submitting = ref(false);

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
  needsPassword.value = false;
  try {
    page.value = await publicApi.share(token());
    applyNoindex(page.value.noindex);
  } catch (e) {
    if (e instanceof ApiRequestError) {
      if (e.status === 401 && e.detail === "password_required") needsPassword.value = true;
      else if (e.status === 404) error.value = "This link is invalid or has expired.";
      else error.value = "Unable to load page.";
    } else {
      error.value = "Unable to load page.";
    }
  } finally {
    loading.value = false;
  }
}

async function submitPassword() {
  submitting.value = true;
  error.value = "";
  try {
    page.value = await publicApi.verifyPassword(token(), password.value);
    needsPassword.value = false;
    applyNoindex(page.value.noindex);
  } catch (e) {
    error.value =
      e instanceof ApiRequestError && e.status === 403
        ? "Incorrect password."
        : "Verification failed.";
  } finally {
    submitting.value = false;
  }
}

onMounted(load);
watch(() => route.params.token, load);
</script>

<template>
  <div class="share-wrap">
    <p v-if="loading" class="muted container">Loading…</p>

    <div v-else-if="needsPassword" class="pw-wrap">
      <form class="card pw-card" @submit.prevent="submitPassword">
        <h2>Password required</h2>
        <input v-model="password" class="input" type="password" placeholder="Password" required />
        <p v-if="error" class="error">{{ error }}</p>
        <button class="btn btn-primary" style="width: 100%; margin-top: 0.5rem" :disabled="submitting">
          Unlock
        </button>
      </form>
    </div>

    <div v-else-if="error" class="container">
      <div class="card">{{ error }}</div>
    </div>

    <article v-else-if="page" class="container reader">
      <DocHeader :title="page.title">
        <template #meta>
          v{{ page.version_number }} · updated {{ new Date(page.updated_at).toLocaleString() }}
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
.share-wrap {
  min-height: 100dvh;
}
.pw-wrap {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 80vh;
  padding: 1rem;
}
.pw-card {
  width: 100%;
  max-width: 340px;
}
.pw-card h2 {
  margin-top: 0;
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

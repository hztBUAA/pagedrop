<script setup lang="ts">
import { onMounted, ref } from "vue";
import { authApi } from "@/api";

const props = defineProps<{ redirect?: string }>();

const providers = ref<string[]>([]);
const busy = ref("");

const LABELS: Record<string, string> = {
  github: "Continue with GitHub",
  google: "Continue with Google",
};

onMounted(async () => {
  try {
    const res = await authApi.oauthProviders();
    providers.value = res.providers.filter((p) => p in LABELS);
  } catch {
    providers.value = [];
  }
});

async function start(provider: string) {
  busy.value = provider;
  try {
    if (props.redirect) {
      sessionStorage.setItem("pd_oauth_redirect", props.redirect);
    } else {
      sessionStorage.removeItem("pd_oauth_redirect");
    }
    const { authorize_url } = await authApi.oauthStart(provider);
    window.location.href = authorize_url;
  } catch {
    busy.value = "";
  }
}
</script>

<template>
  <div v-if="providers.length" class="oauth">
    <div class="divider"><span>or</span></div>
    <button
      v-for="p in providers"
      :key="p"
      class="btn oauth-btn"
      type="button"
      :disabled="!!busy"
      @click="start(p)"
    >
      <span class="icon" :class="`icon-${p}`" aria-hidden="true"></span>
      {{ busy === p ? "Redirecting…" : LABELS[p] }}
    </button>
  </div>
</template>

<style scoped>
.oauth {
  margin-top: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.divider {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  color: var(--muted, #888);
  font-size: 0.85rem;
  margin: 0.25rem 0 0.5rem;
}
.divider::before,
.divider::after {
  content: "";
  flex: 1;
  height: 1px;
  background: var(--border, #e2e2e2);
}
.oauth-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}
.icon {
  width: 18px;
  height: 18px;
  display: inline-block;
  background-size: contain;
  background-repeat: no-repeat;
  background-position: center;
}
.icon-github {
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Cpath d='M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0016 8c0-4.42-3.58-8-8-8z'/%3E%3C/svg%3E");
}
.icon-google {
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'%3E%3Cpath fill='%23FFC107' d='M43.6 20.5H42V20H24v8h11.3c-1.6 4.7-6.1 8-11.3 8-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.3 4.1 29.4 2 24 2 11.8 2 2 11.8 2 24s9.8 22 22 22 22-9.8 22-22c0-1.3-.1-2.3-.4-3.5z'/%3E%3Cpath fill='%23FF3D00' d='M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.3 4.1 29.4 2 24 2 15.9 2 8.8 6.6 6.3 14.7z'/%3E%3Cpath fill='%234CAF50' d='M24 46c5.3 0 10.1-2 13.7-5.3l-6.3-5.3C29.3 36.8 26.8 38 24 38c-5.2 0-9.6-3.3-11.2-8l-6.5 5C8.7 41.4 15.8 46 24 46z'/%3E%3Cpath fill='%231976D2' d='M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.1-4 5.4l6.3 5.3C41.4 36.3 46 30.8 46 24c0-1.3-.1-2.3-.4-3.5z'/%3E%3C/svg%3E");
}
</style>

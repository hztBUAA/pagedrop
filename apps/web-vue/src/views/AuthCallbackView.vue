<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ApiRequestError } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import { useWorkspaceStore } from "@/stores/workspace";

const auth = useAuthStore();
const ws = useWorkspaceStore();
const router = useRouter();
const route = useRoute();

const error = ref("");

onMounted(async () => {
  const code = route.query.code as string | undefined;
  const state = route.query.state as string | undefined;
  const providerError = route.query.error as string | undefined;

  if (providerError) {
    error.value = "Sign-in was cancelled or denied.";
    return;
  }
  if (!code || !state) {
    error.value = "Missing authorization response.";
    return;
  }

  try {
    await auth.completeOAuth(code, state);
    await ws.load();
    const redirect = sessionStorage.getItem("pd_oauth_redirect");
    sessionStorage.removeItem("pd_oauth_redirect");
    router.replace(redirect || { name: "dashboard" });
  } catch (e) {
    if (e instanceof ApiRequestError && e.status === 429) {
      error.value = "Too many attempts. Try again shortly.";
    } else {
      error.value = "Sign-in failed. Please try again.";
    }
  }
});
</script>

<template>
  <div class="auth-wrap">
    <div class="card auth-card">
      <template v-if="error">
        <h1>Sign-in failed</h1>
        <p class="error">{{ error }}</p>
        <router-link class="btn btn-primary" style="width: 100%" :to="{ name: 'login' }">
          Back to sign in
        </router-link>
      </template>
      <template v-else>
        <h1>Signing you in…</h1>
        <p class="muted">Completing authorization, one moment.</p>
      </template>
    </div>
  </div>
</template>

<style scoped>
.auth-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
}
.auth-card {
  width: 100%;
  max-width: 380px;
  text-align: center;
}
h1 {
  margin-top: 0;
}
</style>

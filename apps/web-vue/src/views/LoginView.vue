<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ApiRequestError } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import { useWorkspaceStore } from "@/stores/workspace";

const auth = useAuthStore();
const ws = useWorkspaceStore();
const router = useRouter();
const route = useRoute();

const email = ref("");
const password = ref("");
const error = ref("");
const busy = ref(false);

async function submit() {
  error.value = "";
  busy.value = true;
  try {
    await auth.login(email.value, password.value);
    await ws.load();
    const redirect = route.query.redirect as string | undefined;
    router.push(redirect || { name: "dashboard" });
  } catch (e) {
    if (e instanceof ApiRequestError) {
      error.value =
        e.status === 429 ? "Too many attempts. Try again shortly." : "Invalid email or password.";
    } else {
      error.value = "Login failed.";
    }
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div class="auth-wrap">
    <form class="card auth-card" @submit.prevent="submit">
      <h1>Sign in</h1>
      <div class="field">
        <label>Email</label>
        <input v-model="email" class="input" type="email" autocomplete="email" required />
      </div>
      <div class="field">
        <label>Password</label>
        <input
          v-model="password"
          class="input"
          type="password"
          autocomplete="current-password"
          required
        />
      </div>
      <p v-if="error" class="error">{{ error }}</p>
      <button class="btn btn-primary" style="width: 100%" :disabled="busy" type="submit">
        {{ busy ? "Signing in…" : "Sign in" }}
      </button>
      <p class="muted" style="margin-top: 1rem; text-align: center">
        No account? <router-link :to="{ name: 'register' }">Register</router-link>
        · <router-link :to="{ name: 'reset-password' }">Forgot password?</router-link>
      </p>
    </form>
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
}
h1 {
  margin-top: 0;
}
</style>

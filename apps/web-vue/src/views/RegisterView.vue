<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { ApiRequestError } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import { useWorkspaceStore } from "@/stores/workspace";

const auth = useAuthStore();
const ws = useWorkspaceStore();
const router = useRouter();

const email = ref("");
const password = ref("");
const name = ref("");
const error = ref("");
const busy = ref(false);

async function submit() {
  error.value = "";
  if (password.value.length < 8) {
    error.value = "Password must be at least 8 characters.";
    return;
  }
  busy.value = true;
  try {
    await auth.register(email.value, password.value, name.value || undefined);
    await ws.load();
    router.push({ name: "dashboard" });
  } catch (e) {
    if (e instanceof ApiRequestError) {
      if (e.status === 409) error.value = "That email is already registered.";
      else if (e.status === 429) error.value = "Too many attempts. Try again shortly.";
      else error.value = "Registration failed.";
    } else {
      error.value = "Registration failed.";
    }
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div class="auth-wrap">
    <form class="card auth-card" @submit.prevent="submit">
      <h1>Create account</h1>
      <div class="field">
        <label>Name (optional)</label>
        <input v-model="name" class="input" type="text" autocomplete="name" />
      </div>
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
          autocomplete="new-password"
          required
        />
      </div>
      <p v-if="error" class="error">{{ error }}</p>
      <button class="btn btn-primary" style="width: 100%" :disabled="busy" type="submit">
        {{ busy ? "Creating…" : "Create account" }}
      </button>
      <p class="muted" style="margin-top: 1rem; text-align: center">
        Have an account? <router-link :to="{ name: 'login' }">Sign in</router-link>
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

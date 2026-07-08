<script setup lang="ts">
import { onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ApiRequestError } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import { useWorkspaceStore } from "@/stores/workspace";

const auth = useAuthStore();
const ws = useWorkspaceStore();
const router = useRouter();

const email = ref("");
const code = ref("");
const newPassword = ref("");
const error = ref("");
const notice = ref("");
const busy = ref(false);
const sendingCode = ref(false);
const cooldown = ref(0);
let timer: ReturnType<typeof setInterval> | null = null;

function startCooldown() {
  cooldown.value = 60;
  timer = setInterval(() => {
    cooldown.value -= 1;
    if (cooldown.value <= 0 && timer) {
      clearInterval(timer);
      timer = null;
    }
  }, 1000);
}
onUnmounted(() => timer && clearInterval(timer));

async function sendCode() {
  error.value = "";
  notice.value = "";
  if (!email.value) {
    error.value = "Enter your email first.";
    return;
  }
  sendingCode.value = true;
  try {
    await auth.requestCode(email.value, "reset");
    notice.value = "If that email has an account, a reset code was sent.";
    startCooldown();
  } catch (e) {
    if (e instanceof ApiRequestError && e.status === 429) {
      error.value = "Please wait before requesting another code.";
    } else {
      error.value = "Failed to send code.";
    }
  } finally {
    sendingCode.value = false;
  }
}

async function submit() {
  error.value = "";
  if (!code.value) {
    error.value = "Enter the verification code sent to your email.";
    return;
  }
  if (newPassword.value.length < 8) {
    error.value = "Password must be at least 8 characters.";
    return;
  }
  busy.value = true;
  try {
    await auth.resetPassword(email.value, code.value, newPassword.value);
    await ws.load();
    router.push({ name: "dashboard" });
  } catch (e) {
    if (e instanceof ApiRequestError) {
      if (e.status === 400) error.value = "Invalid or expired verification code.";
      else if (e.status === 429) error.value = "Too many attempts. Try again shortly.";
      else error.value = "Password reset failed.";
    } else {
      error.value = "Password reset failed.";
    }
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div class="auth-wrap">
    <form class="card auth-card" @submit.prevent="submit">
      <h1>Reset password</h1>
      <div class="field">
        <label>Email</label>
        <div class="row">
          <input
            v-model="email"
            class="input grow"
            type="email"
            autocomplete="email"
            required
          />
          <button
            type="button"
            class="btn btn-sm"
            :disabled="sendingCode || cooldown > 0"
            @click="sendCode"
          >
            {{ cooldown > 0 ? `${cooldown}s` : sendingCode ? "Sending…" : "Send code" }}
          </button>
        </div>
      </div>
      <div class="field">
        <label>Verification code</label>
        <input
          v-model="code"
          class="input"
          inputmode="numeric"
          maxlength="6"
          autocomplete="one-time-code"
          placeholder="6-digit code"
          required
        />
      </div>
      <div class="field">
        <label>New password</label>
        <input
          v-model="newPassword"
          class="input"
          type="password"
          autocomplete="new-password"
          required
        />
      </div>
      <p v-if="notice" class="muted" style="color: var(--success)">{{ notice }}</p>
      <p v-if="error" class="error">{{ error }}</p>
      <button class="btn btn-primary" style="width: 100%" :disabled="busy" type="submit">
        {{ busy ? "Resetting…" : "Reset password" }}
      </button>
      <p class="muted" style="margin-top: 1rem; text-align: center">
        Remembered it? <router-link :to="{ name: 'login' }">Sign in</router-link>
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

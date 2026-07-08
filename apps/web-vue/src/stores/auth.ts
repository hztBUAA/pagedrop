import { defineStore } from "pinia";
import { ref } from "vue";
import { authApi } from "@/api";
import type { User } from "@/api/types";

export const useAuthStore = defineStore("auth", () => {
  const user = ref<User | null>(null);
  const ready = ref(false);

  async function fetchMe() {
    try {
      user.value = await authApi.me();
    } catch {
      user.value = null;
    } finally {
      ready.value = true;
    }
  }

  async function login(email: string, password: string) {
    user.value = await authApi.login(email, password);
  }

  async function requestCode(email: string, purpose: "register" | "reset" = "register") {
    await authApi.requestCode(email, purpose);
  }

  async function register(email: string, password: string, code: string, name?: string) {
    user.value = await authApi.register(email, password, code, name);
  }

  async function resetPassword(email: string, code: string, newPassword: string) {
    user.value = await authApi.resetPassword(email, code, newPassword);
  }

  async function logout() {
    await authApi.logout();
    user.value = null;
  }

  async function completeOAuth(code: string, state: string) {
    user.value = await authApi.oauthCallback(code, state);
  }

  return {
    user,
    ready,
    fetchMe,
    login,
    requestCode,
    register,
    resetPassword,
    logout,
    completeOAuth,
  };
});

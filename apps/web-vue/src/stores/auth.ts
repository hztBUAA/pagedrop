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

  async function register(email: string, password: string, name?: string) {
    user.value = await authApi.register(email, password, name);
  }

  async function logout() {
    await authApi.logout();
    user.value = null;
  }

  return { user, ready, fetchMe, login, register, logout };
});

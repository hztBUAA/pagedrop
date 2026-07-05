<script setup lang="ts">
import { onMounted } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { useWorkspaceStore } from "@/stores/workspace";

const auth = useAuthStore();
const ws = useWorkspaceStore();
const router = useRouter();

onMounted(() => {
  if (!ws.loaded) ws.load();
});

async function onLogout() {
  await auth.logout();
  ws.reset();
  router.push({ name: "login" });
}

function onSwitchWorkspace(e: Event) {
  ws.setCurrent((e.target as HTMLSelectElement).value);
}
</script>

<template>
  <header class="nav">
    <div class="nav-inner container">
      <router-link :to="{ name: 'dashboard' }" class="brand">PageDrop</router-link>
      <div class="grow" />
      <select
        v-if="ws.workspaces.length"
        class="select ws-select"
        :value="ws.currentId ?? ''"
        @change="onSwitchWorkspace"
      >
        <option v-for="w in ws.workspaces" :key="w.id" :value="w.id">
          {{ w.name }} ({{ w.role }})
        </option>
      </select>
      <router-link :to="{ name: 'new-page' }" class="btn btn-sm">+ New</router-link>
      <router-link :to="{ name: 'tokens' }" class="btn btn-sm hide-mobile">Tokens</router-link>
      <button class="btn btn-sm" @click="onLogout">Logout</button>
    </div>
  </header>
</template>

<style scoped>
.nav {
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  position: sticky;
  top: 0;
  z-index: 10;
}
.nav-inner {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding-top: 0.6rem;
  padding-bottom: 0.6rem;
}
.brand {
  font-weight: 700;
  font-size: 1.15rem;
  color: var(--text);
}
.ws-select {
  width: auto;
  max-width: 200px;
  padding: 0.35rem 0.5rem;
}
</style>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import { useWorkspaceStore } from "@/stores/workspace";

const auth = useAuthStore();
const ws = useWorkspaceStore();
const router = useRouter();

// Mobile: the actions collapse behind a hamburger so the bar never overflows.
const open = ref(false);

onMounted(() => {
  if (!ws.loaded) ws.load();
});

async function onLogout() {
  open.value = false;
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
      <router-link :to="{ name: 'dashboard' }" class="brand" @click="open = false">
        PageDrop
      </router-link>
      <div class="grow" />
      <button
        type="button"
        class="nav-toggle"
        :aria-expanded="open"
        aria-label="Menu"
        @click="open = !open"
      >
        <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
          <path
            :d="open ? 'M6 6l12 12M18 6L6 18' : 'M4 7h16M4 12h16M4 17h16'"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
          />
        </svg>
      </button>
      <nav class="nav-menu" :class="{ open }">
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
        <router-link :to="{ name: 'new-page' }" class="btn btn-sm" @click="open = false">
          + New
        </router-link>
        <router-link :to="{ name: 'tokens' }" class="btn btn-sm" @click="open = false">
          Tokens
        </router-link>
        <button class="btn btn-sm" @click="onLogout">Logout</button>
      </nav>
    </div>
  </header>
</template>

<style scoped>
.nav {
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  position: sticky;
  top: 0;
  z-index: 30;
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
.nav-menu {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.ws-select {
  width: auto;
  max-width: 200px;
  padding: 0.35rem 0.5rem;
}
.nav-toggle {
  display: none;
  width: 38px;
  height: 38px;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface-2);
  color: var(--text);
  padding: 0;
}

@media (max-width: 640px) {
  .nav-toggle {
    display: inline-flex;
  }
  /* Collapsed dropdown: overlays content instead of pushing the page. */
  .nav-menu {
    display: none;
    position: absolute;
    left: 0;
    right: 0;
    top: 100%;
    flex-direction: column;
    align-items: stretch;
    gap: 0.5rem;
    padding: 0.75rem 1rem;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    box-shadow: 0 8px 20px rgba(0, 0, 0, 0.35);
  }
  .nav-menu.open {
    display: flex;
  }
  .ws-select {
    max-width: none;
    width: 100%;
  }
}
</style>

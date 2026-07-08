<script setup lang="ts">
import { ref } from "vue";

defineProps<{ title: string }>();

// On mobile the meta + actions are collapsed behind the toggle so the reading
// area gets the full screen. On desktop CSS keeps them permanently visible.
const expanded = ref(false);
</script>

<template>
  <header class="doc-head" :class="{ expanded }">
    <div class="doc-bar">
      <h1 class="doc-title">{{ title }}</h1>
      <button
        type="button"
        class="doc-toggle"
        :aria-expanded="expanded"
        aria-label="Toggle details"
        @click="expanded = !expanded"
      >
        <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
          <path
            d="M6 9l6 6 6-6"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </button>
    </div>
    <div class="doc-details">
      <div class="doc-meta"><slot name="meta" /></div>
      <div class="doc-actions"><slot name="actions" /></div>
    </div>
  </header>
</template>

<style scoped>
.doc-head {
  position: sticky;
  top: 0;
  z-index: 20;
  background: color-mix(in srgb, var(--bg) 85%, transparent);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--border);
  margin-bottom: 1rem;
}
.doc-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6rem 0;
}
.doc-title {
  margin: 0;
  flex: 1;
  min-width: 0;
  font-size: 1.35rem;
  line-height: 1.3;
}
.doc-toggle {
  display: none;
  flex: none;
  width: 34px;
  height: 34px;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface-2);
  color: var(--text-dim);
  padding: 0;
  transition: color 0.15s, transform 0.2s ease;
}
.doc-toggle:hover {
  color: var(--text);
}
.doc-details {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
  padding-bottom: 0.6rem;
}
.doc-meta {
  color: var(--text-dim);
  font-size: 0.82rem;
}
.doc-actions {
  display: flex;
  gap: 0.5rem;
}

@media (max-width: 640px) {
  .doc-head {
    margin-bottom: 0.6rem;
  }
  .doc-title {
    font-size: 1.05rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .doc-toggle {
    display: inline-flex;
  }
  .doc-head.expanded .doc-toggle {
    transform: rotate(180deg);
  }
  /* Collapsed by default on mobile: reclaim the space for content. */
  .doc-details {
    display: none;
    flex-direction: column;
    align-items: stretch;
    padding-top: 0.1rem;
  }
  .doc-head.expanded .doc-details {
    display: flex;
  }
  .doc-actions {
    flex-wrap: wrap;
  }
}
</style>

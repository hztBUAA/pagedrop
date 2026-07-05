<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  contentType: string;
  sourceContent: string;
  renderedHtml: string | null;
}>();

// sandbox_html is never trusted: render inside a fully sandboxed iframe with
// no allow-scripts so nothing executes with page privileges.
const isSandbox = computed(() => props.contentType === "sandbox_html");
const isSafeHtml = computed(() => props.contentType === "safe_html");
const isMarkdown = computed(() => props.contentType === "markdown");
</script>

<template>
  <div class="renderer">
    <!-- safe_html: server-sanitized (nh3), no scripts -->
    <div v-if="isSafeHtml && renderedHtml" class="prose" v-html="renderedHtml" />

    <!-- sandbox_html: isolated iframe, scripts disabled -->
    <iframe
      v-else-if="isSandbox"
      class="sandbox"
      sandbox=""
      referrerpolicy="no-referrer"
      :srcdoc="sourceContent"
      title="sandboxed content"
    />

    <!-- markdown: Phase 4 shows source; Phase 5 mounts the React renderer -->
    <pre v-else-if="isMarkdown" class="source">{{ sourceContent }}</pre>

    <div v-else class="muted">Nothing to render.</div>
  </div>
</template>

<style scoped>
.renderer {
  overflow-wrap: anywhere;
}
.sandbox {
  width: 100%;
  min-height: 70vh;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: #fff;
}
.source {
  white-space: pre-wrap;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 1rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.9rem;
}
.prose {
  line-height: 1.6;
}
:deep(.prose img) {
  max-width: 100%;
}
:deep(.prose pre) {
  overflow-x: auto;
}
</style>

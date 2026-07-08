<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from "vue";

const props = defineProps<{
  contentType: string;
  sourceContent: string;
  renderedHtml: string | null;
}>();

// The React artifact renderer is served here. In dev, point at its Vite server
// via VITE_RENDERER_URL (e.g. http://localhost:5175); in prod it is mounted at /render/.
const RENDERER_URL = (import.meta.env.VITE_RENDERER_URL as string | undefined) ?? "/render/";
const rendererOrigin = new URL(RENDERER_URL, window.location.origin).origin;

const frame = ref<HTMLIFrameElement | null>(null);
const frameHeight = ref(240);
let ready = false;

function payload() {
  return {
    type: "render",
    payload: {
      contentType: props.contentType,
      sourceContent: props.sourceContent,
      renderedHtml: props.renderedHtml,
    },
  };
}

function send() {
  if (ready && frame.value?.contentWindow) {
    frame.value.contentWindow.postMessage(payload(), rendererOrigin);
  }
}

function onMessage(e: MessageEvent) {
  if (e.source !== frame.value?.contentWindow) return;
  const data = e.data;
  if (data?.source !== "pagedrop-renderer") return;
  if (data.type === "ready") {
    ready = true;
    send();
  } else if (data.type === "height" && typeof data.height === "number") {
    frameHeight.value = Math.max(120, Math.ceil(data.height) + 8);
  }
}

window.addEventListener("message", onMessage);
onBeforeUnmount(() => window.removeEventListener("message", onMessage));

// Re-send whenever the content changes (e.g. switching versions).
watch(() => [props.contentType, props.sourceContent, props.renderedHtml], send);
</script>

<template>
  <div class="renderer">
    <iframe
      ref="frame"
      class="render-frame"
      :src="RENDERER_URL"
      sandbox="allow-scripts allow-same-origin"
      referrerpolicy="no-referrer"
      title="rendered content"
      :style="{ height: frameHeight + 'px' }"
    />
  </div>
</template>

<style scoped>
.renderer {
  overflow-wrap: anywhere;
}
.render-frame {
  width: 100%;
  border: none;
  display: block;
  background: transparent;
}
</style>

<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from "vue";

import { assetUrl } from "../api/client";

interface Anchor {
  id: string;
  quote: string;
  prefix: string;
  suffix: string;
}

const props = defineProps<{
  contentType: string;
  sourceContent: string;
  renderedHtml: string | null;
  publicView?: boolean;
  shareToken?: string | null;
  anchors?: Anchor[];
  focusedAnchorId?: string | null;
}>();

const emit = defineEmits<{
  select: [sel: { quote: string; prefix: string; suffix: string } | null];
  anchorClick: [commentId: string];
}>();

const ASSET_REF = /pagedrop:\/\/asset\/([0-9a-fA-F-]{8,})/g;

function resolveAssets(text: string | null): string | null {
  if (!text) return text;
  return text.replace(ASSET_REF, (_m, id: string) =>
    assetUrl(id, props.publicView ?? false, props.shareToken),
  );
}

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
      sourceContent: resolveAssets(props.sourceContent),
      renderedHtml: resolveAssets(props.renderedHtml),
    },
  };
}

function send() {
  if (ready && frame.value?.contentWindow) {
    frame.value.contentWindow.postMessage(payload(), rendererOrigin);
  }
}

function sendHighlights() {
  if (ready && frame.value?.contentWindow) {
    frame.value.contentWindow.postMessage(
      { type: "highlights", anchors: props.anchors ?? [] },
      rendererOrigin,
    );
  }
}

function sendFocus() {
  if (ready && frame.value?.contentWindow) {
    frame.value.contentWindow.postMessage(
      { type: "focus-anchor", id: props.focusedAnchorId ?? null },
      rendererOrigin,
    );
  }
}

function onMessage(e: MessageEvent) {
  if (e.source !== frame.value?.contentWindow) return;
  const data = e.data;
  if (data?.source !== "pagedrop-renderer") return;
  if (data.type === "ready") {
    ready = true;
    send();
    sendHighlights();
    sendFocus();
  } else if (data.type === "height" && typeof data.height === "number") {
    frameHeight.value = Math.max(120, Math.ceil(data.height) + 8);
  } else if (data.type === "selection") {
    const quote = typeof data.quote === "string" ? data.quote : "";
    emit(
      "select",
      quote ? { quote, prefix: data.prefix ?? "", suffix: data.suffix ?? "" } : null,
    );
  } else if (data.type === "anchor-click" && typeof data.commentId === "string") {
    emit("anchorClick", data.commentId);
  }
}

window.addEventListener("message", onMessage);
onBeforeUnmount(() => window.removeEventListener("message", onMessage));

// Re-send whenever the content changes (e.g. switching versions).
watch(() => [props.contentType, props.sourceContent, props.renderedHtml], send);
watch(() => props.anchors, sendHighlights, { deep: true });
watch(() => props.focusedAnchorId, sendFocus);
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

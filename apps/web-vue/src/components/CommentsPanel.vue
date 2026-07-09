<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { commentApi } from "@/api";
import { ApiRequestError } from "@/api/client";
import type { Comment } from "@/api/types";
import { useAuthStore } from "@/stores/auth";

interface PendingAnchor {
  quote: string;
  prefix: string;
  suffix: string;
}

const props = defineProps<{
  ws: string;
  slug: string;
  pendingAnchor?: PendingAnchor | null;
  activeVersion?: number | null;
  focusedId?: string | null;
  // "public" gates commenting behind login and hides moderation (resolve/delete).
  mode?: "manage" | "public";
  // Present on share-link pages; authorizes commenting on private shared pages.
  shareToken?: string | null;
}>();

const emit = defineEmits<{
  clearAnchor: [];
  focus: [id: string | null];
  loaded: [comments: Comment[]];
  jumpVersion: [n: number];
}>();

const auth = useAuthStore();
const route = useRoute();

const isPublic = computed(() => props.mode === "public");
const canModerate = computed(() => !isPublic.value);
const needsLogin = computed(() => isPublic.value && !auth.user);
const loginTo = computed(() => ({ name: "login", query: { redirect: route.fullPath } }));

const comments = ref<Comment[]>([]);
const loading = ref(false);
const error = ref("");
const filter = ref<"open" | "resolved" | "all">("open");

const newBody = ref("");
const posting = ref(false);
const replyOpen = ref<string | null>(null);
const replyBody = ref("");

const roots = computed(() => comments.value.filter((c) => !c.thread_root_id));
function repliesOf(rootId: string) {
  return comments.value.filter((c) => c.thread_root_id === rootId);
}

async function load() {
  if (needsLogin.value) {
    comments.value = [];
    emit("loaded", []);
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    const status = filter.value === "all" ? undefined : filter.value;
    comments.value = await commentApi.list(props.ws, props.slug, status, props.shareToken);
    emit("loaded", comments.value);
  } catch {
    error.value = "Failed to load comments.";
  } finally {
    loading.value = false;
  }
}

async function post() {
  if (!newBody.value.trim()) return;
  posting.value = true;
  error.value = "";
  try {
    const anchor = props.pendingAnchor;
    await commentApi.create(
      props.ws,
      props.slug,
      {
        body: newBody.value.trim(),
        ...(anchor
          ? {
              anchor_quote: anchor.quote,
              anchor_prefix: anchor.prefix,
              anchor_suffix: anchor.suffix,
              anchor_version_number: props.activeVersion ?? null,
            }
          : {}),
      },
      props.shareToken,
    );
    newBody.value = "";
    emit("clearAnchor");
    await load();
  } catch (e) {
    error.value = e instanceof ApiRequestError ? String(e.detail) : "Post failed.";
  } finally {
    posting.value = false;
  }
}

async function reply(rootId: string) {
  if (!replyBody.value.trim()) return;
  posting.value = true;
  try {
    await commentApi.create(
      props.ws,
      props.slug,
      { body: replyBody.value.trim(), thread_root_id: rootId },
      props.shareToken,
    );
    replyBody.value = "";
    replyOpen.value = null;
    await load();
  } finally {
    posting.value = false;
  }
}

async function toggleStatus(c: Comment) {
  if (c.status === "resolved") await commentApi.reopen(c.id);
  else await commentApi.resolve(c.id);
  await load();
}

async function remove(id: string) {
  if (!confirm("Delete this comment and its replies?")) return;
  await commentApi.del(id);
  await load();
}

onMounted(load);
watch(filter, load);
watch(() => auth.user, load);
watch(
  () => props.focusedId,
  (id) => {
    if (!id) return;
    requestAnimationFrame(() =>
      document
        .getElementById("comment-" + id)
        ?.scrollIntoView({ behavior: "smooth", block: "center" }),
    );
  },
);
</script>

<template>
  <div class="stack">
    <div v-if="needsLogin" class="card stack">
      <strong>Comments</strong>
      <p class="muted">Log in to read and post comments on this page.</p>
      <div>
        <router-link :to="loginTo" class="btn btn-primary btn-sm">Log in to comment</router-link>
      </div>
    </div>

    <template v-else>
      <form class="card stack" @submit.prevent="post">
        <strong>Add a comment</strong>
        <div v-if="pendingAnchor" class="pending-anchor">
          <blockquote class="anchor">{{ pendingAnchor.quote }}</blockquote>
          <button type="button" class="btn btn-sm clear-anchor" @click="emit('clearAnchor')">
            Clear
          </button>
        </div>
        <textarea
          v-model="newBody"
          class="input"
          rows="3"
          :placeholder="
            pendingAnchor ? 'Comment on the selected text…' : 'Leave feedback on this document…'
          "
        />
        <div>
          <button class="btn btn-primary" :disabled="posting" type="submit">Post</button>
        </div>
      </form>

      <div class="row wrap" style="gap: 0.4rem">
        <button
          v-for="f in (['open', 'resolved', 'all'] as const)"
          :key="f"
          class="btn btn-sm"
          :class="{ 'btn-primary': filter === f }"
          @click="filter = f"
        >
          {{ f }}
        </button>
      </div>

      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="loading" class="muted">Loading…</p>
      <p v-else-if="roots.length === 0" class="muted">No comments yet.</p>

      <div
        v-for="c in roots"
        :id="'comment-' + c.id"
        :key="c.id"
        class="card stack thread"
        :class="{ anchored: !!c.anchor_quote, focused: focusedId === c.id }"
        @click="c.anchor_quote && emit('focus', c.id)"
      >
        <div class="row between wrap">
          <div class="grow">
            <div class="c-meta muted">
              <strong>{{ c.author_display ?? "?" }}</strong>
              <span class="badge" :class="{ private: c.status === 'resolved' }">{{ c.status }}</span>
              <button
                v-if="
                  c.anchor_version_number != null &&
                  activeVersion != null &&
                  c.anchor_version_number !== activeVersion
                "
                type="button"
                class="badge unlisted ver-badge"
                :title="`Anchored to v${c.anchor_version_number} — click to view`"
                @click.stop="emit('jumpVersion', c.anchor_version_number as number)"
              >
                on v{{ c.anchor_version_number }}
              </button>
              · {{ new Date(c.created_at).toLocaleString() }}
            </div>
            <blockquote v-if="c.anchor_quote" class="anchor">{{ c.anchor_quote }}</blockquote>
            <p class="c-body">{{ c.body }}</p>
          </div>
        </div>

        <div v-for="r in repliesOf(c.id)" :key="r.id" class="reply">
          <div class="c-meta muted">
            <strong>{{ r.author_display ?? "?" }}</strong>
            · {{ new Date(r.created_at).toLocaleString() }}
          </div>
          <p class="c-body">{{ r.body }}</p>
        </div>

        <div v-if="replyOpen === c.id" class="stack" @click.stop>
          <textarea v-model="replyBody" class="input" rows="2" placeholder="Reply…" />
          <div class="row" style="gap: 0.4rem">
            <button class="btn btn-sm btn-primary" :disabled="posting" @click="reply(c.id)">
              Send
            </button>
            <button class="btn btn-sm" @click="replyOpen = null">Cancel</button>
          </div>
        </div>

        <div class="row wrap" style="gap: 0.4rem" @click.stop>
          <button v-if="replyOpen !== c.id" class="btn btn-sm" @click="replyOpen = c.id">
            Reply
          </button>
          <button v-if="canModerate" class="btn btn-sm" @click="toggleStatus(c)">
            {{ c.status === "resolved" ? "Reopen" : "Resolve" }}
          </button>
          <button v-if="canModerate" class="btn btn-sm btn-danger" @click="remove(c.id)">
            Delete
          </button>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.thread {
  gap: 0.6rem;
}
.thread.anchored {
  cursor: pointer;
}
.thread.focused {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent) inset;
}
.pending-anchor {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
}
.pending-anchor .anchor {
  flex: 1;
  margin: 0;
  border-left-color: var(--accent);
}
.clear-anchor {
  flex: none;
}
.c-meta {
  font-size: 0.8rem;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem;
}
.c-body {
  margin: 0.3rem 0 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.anchor {
  margin: 0.4rem 0 0;
  padding: 0.2rem 0.6rem;
  border-left: 3px solid var(--border);
  color: var(--text-dim);
  font-size: 0.85rem;
}
.reply {
  border-left: 2px solid var(--border);
  padding-left: 0.7rem;
  margin-left: 0.3rem;
}
.ver-badge {
  cursor: pointer;
  border: none;
  font: inherit;
}
</style>

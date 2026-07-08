<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { commentApi } from "@/api";
import { ApiRequestError } from "@/api/client";
import type { Comment } from "@/api/types";

const props = defineProps<{ ws: string; slug: string }>();

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
  loading.value = true;
  error.value = "";
  try {
    const status = filter.value === "all" ? undefined : filter.value;
    comments.value = await commentApi.list(props.ws, props.slug, status);
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
    await commentApi.create(props.ws, props.slug, { body: newBody.value.trim() });
    newBody.value = "";
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
    await commentApi.create(props.ws, props.slug, {
      body: replyBody.value.trim(),
      thread_root_id: rootId,
    });
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
</script>

<template>
  <div class="stack">
    <form class="card stack" @submit.prevent="post">
      <strong>Add a comment</strong>
      <textarea
        v-model="newBody"
        class="input"
        rows="3"
        placeholder="Leave feedback on this document…"
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

    <div v-for="c in roots" :key="c.id" class="card stack thread">
      <div class="row between wrap">
        <div class="grow">
          <div class="c-meta muted">
            <strong>{{ c.author_display ?? "?" }}</strong>
            <span class="badge" :class="{ private: c.status === 'resolved' }">{{ c.status }}</span>
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

      <div v-if="replyOpen === c.id" class="stack">
        <textarea v-model="replyBody" class="input" rows="2" placeholder="Reply…" />
        <div class="row" style="gap: 0.4rem">
          <button class="btn btn-sm btn-primary" :disabled="posting" @click="reply(c.id)">
            Send
          </button>
          <button class="btn btn-sm" @click="replyOpen = null">Cancel</button>
        </div>
      </div>

      <div class="row wrap" style="gap: 0.4rem">
        <button v-if="replyOpen !== c.id" class="btn btn-sm" @click="replyOpen = c.id">
          Reply
        </button>
        <button class="btn btn-sm" @click="toggleStatus(c)">
          {{ c.status === "resolved" ? "Reopen" : "Resolve" }}
        </button>
        <button class="btn btn-sm btn-danger" @click="remove(c.id)">Delete</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.thread {
  gap: 0.6rem;
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
</style>

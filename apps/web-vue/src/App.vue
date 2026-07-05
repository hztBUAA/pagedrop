<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";
import NavBar from "@/components/NavBar.vue";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const route = useRoute();
const showNav = computed(() => !!auth.user && !route.meta.public);
</script>

<template>
  <NavBar v-if="showNav" />
  <main>
    <router-view />
  </main>
</template>

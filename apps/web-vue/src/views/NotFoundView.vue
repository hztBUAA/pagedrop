<script setup lang="ts">
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
</script>

<template>
  <div class="container nf">
    <h1>404</h1>
    <p class="muted">This page could not be found.</p>
    <router-link :to="auth.user ? { name: 'dashboard' } : { name: 'login' }" class="btn btn-primary">
      Go home
    </router-link>
  </div>
</template>

<style scoped>
.nf {
  text-align: center;
  padding-top: 4rem;
}
.nf h1 {
  font-size: 3rem;
  margin-bottom: 0.5rem;
}
</style>

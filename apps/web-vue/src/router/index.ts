import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/login",
      name: "login",
      component: () => import("@/views/LoginView.vue"),
      meta: { public: true },
    },
    {
      path: "/register",
      name: "register",
      component: () => import("@/views/RegisterView.vue"),
      meta: { public: true },
    },
    {
      path: "/reset-password",
      name: "reset-password",
      component: () => import("@/views/ResetPasswordView.vue"),
      meta: { public: true },
    },
    {
      path: "/",
      name: "dashboard",
      component: () => import("@/views/DashboardView.vue"),
    },
    {
      path: "/new",
      name: "new-page",
      component: () => import("@/views/NewPageView.vue"),
    },
    {
      path: "/tokens",
      name: "tokens",
      component: () => import("@/views/TokensView.vue"),
    },
    {
      path: "/manage/:ws/:slug",
      name: "project-manage",
      component: () => import("@/views/ProjectView.vue"),
    },
    {
      path: "/p/:ws/:slug",
      name: "project",
      component: () => import("@/views/PublicPageView.vue"),
      meta: { public: true },
    },
    {
      path: "/p/:ws/:slug/v/:version",
      name: "project-version",
      component: () => import("@/views/PublicPageView.vue"),
      meta: { public: true },
    },
    {
      path: "/share/:token",
      name: "share",
      component: () => import("@/views/ShareView.vue"),
      meta: { public: true },
    },
    {
      path: "/about",
      name: "about",
      component: () => import("@/views/AboutView.vue"),
      meta: { public: true },
    },
    {
      path: "/:pathMatch(.*)*",
      name: "not-found",
      component: () => import("@/views/NotFoundView.vue"),
      meta: { public: true },
    },
  ],
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (!auth.ready) {
    await auth.fetchMe();
  }
  if (!to.meta.public && !auth.user) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
  if ((to.name === "login" || to.name === "register") && auth.user) {
    return { name: "dashboard" };
  }
  return true;
});

export default router;

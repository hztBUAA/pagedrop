import { defineStore } from "pinia";
import { ref } from "vue";
import { workspaceApi } from "@/api";
import type { Workspace } from "@/api/types";

export const useWorkspaceStore = defineStore("workspace", () => {
  const workspaces = ref<Workspace[]>([]);
  const currentId = ref<string | null>(
    localStorage.getItem("pd_current_workspace"),
  );
  const loaded = ref(false);

  async function load() {
    workspaces.value = await workspaceApi.list();
    if (!currentId.value && workspaces.value.length > 0) {
      setCurrent(workspaces.value[0].id);
    } else if (
      currentId.value &&
      !workspaces.value.some((w) => w.id === currentId.value)
    ) {
      setCurrent(workspaces.value[0]?.id ?? null);
    }
    loaded.value = true;
  }

  function setCurrent(id: string | null) {
    currentId.value = id;
    if (id) localStorage.setItem("pd_current_workspace", id);
    else localStorage.removeItem("pd_current_workspace");
  }

  function current(): Workspace | null {
    return workspaces.value.find((w) => w.id === currentId.value) ?? null;
  }

  async function create(name: string) {
    const ws = await workspaceApi.create(name);
    workspaces.value.push(ws);
    setCurrent(ws.id);
    return ws;
  }

  function reset() {
    workspaces.value = [];
    loaded.value = false;
  }

  return { workspaces, currentId, loaded, load, setCurrent, current, create, reset };
});

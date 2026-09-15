<script setup>
  import { computed, onMounted, onUnmounted, ref } from "vue";

  import DownloadsView from "@/components/DownloadsView.vue";
  import FetchView from "@/components/FetchView.vue";
  import HistoryView from "@/components/HistoryView.vue";
  import Icon from "@/components/Icon.vue";

  import { useDownloadStore } from "@/stores/downloads.js";
  import { useHistoryStore } from "@/stores/history.js";
  import { extractor, useSessionStore } from "@/stores/session.js";

  const session = useSessionStore();
  const downloads = useDownloadStore();
  const history = useHistoryStore();

  const TABS = [
    { id: "fetch", label: "Fetch", icon: "search" },
    { id: "downloads", label: "Downloads", icon: "download" },
    { id: "history", label: "History", icon: "clock" }
  ];

  const tab = ref("fetch");

  const activeCount = computed(() => downloads.active.length);

  onMounted(async () => {
    await session.start();

    if (session.status !== "ready") {
      return;
    }

    await Promise.all([downloads.attach(), history.load()]);
  });

  // KIKX can tear the iframe down at any time, but stopping the poll loop on
  // unmount keeps development reloads from leaving timers behind.
  onUnmounted(() => {
    if (session.status === "ready") {
      extractor().stop();
    }
  });
</script>

<template>
  <div class="flex h-full flex-col bg-base-100 text-base-content">
    <main class="min-h-0 flex-1">
      <div
        v-if="session.status === 'starting'"
        class="flex h-full items-center justify-center"
      >
        <span class="loading loading-spinner loading-lg text-primary" />
      </div>

      <FetchView v-else-if="tab === 'fetch'" />
      <DownloadsView v-else-if="tab === 'downloads'" />
      <HistoryView v-else @opened="tab = 'fetch'" />
    </main>

    <nav class="flex shrink-0 border-t border-base-300 bg-base-100">
      <button
        v-for="item in TABS"
        :key="item.id"
        type="button"
        class="tab-button"
        :aria-current="tab === item.id ? 'page' : undefined"
        @click="tab = item.id"
      >
        <span class="relative">
          <Icon :name="item.icon" :size="22" />
          <span
            v-if="item.id === 'downloads' && activeCount > 0"
            class="absolute -right-2 -top-1 grid h-4 min-w-4 place-items-center rounded-full bg-primary px-1 text-[0.6rem] font-bold text-primary-content"
          >
            {{ activeCount }}
          </span>
        </span>
        {{ item.label }}
      </button>
    </nav>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import UrlBar from "@/components/UrlBar.vue";
import MediaResult from "@/components/MediaResult.vue";
import DownloadPanel from "@/components/DownloadPanel.vue";
import HistoryList from "@/components/HistoryList.vue";
import { useResolveStore } from "@/stores/resolve.js";
import { useHistoryStore } from "@/stores/history.js";
import { connectRuntime, hasKikx } from "@/services/runtime.js";
import { messageForError } from "@/media/errors.js";

const resolve = useResolveStore();
const history = useHistoryStore();
const runtimeReady = ref(false);
const inKikx = ref(false);

onMounted(async () => {
  await connectRuntime();
  inKikx.value = hasKikx();
  runtimeReady.value = true;
  await history.hydrate();
});
</script>

<template>
  <div class="app">
    <header class="mast">
      <p class="mark">FetchTube</p>
      <p class="lede">Resolve a URL, inspect formats, play or download.</p>
    </header>

    <UrlBar />

    <p v-if="resolve.status === 'resolving'" class="status" role="status">
      Resolving media…
    </p>
    <p v-else-if="resolve.status === 'error'" class="error" role="alert">
      {{ messageForError(resolve.error) }}
    </p>
    <p v-else-if="resolve.status === 'idle'" class="muted empty">
      Paste a link from a site yt-dlp supports.
    </p>

    <MediaResult />
    <DownloadPanel />
    <HistoryList />

    <p v-if="runtimeReady && !inKikx" class="muted footnote">
      Running outside KIKX. Extraction uses the local yt-dlp helper when it is
      available.
    </p>
  </div>
</template>

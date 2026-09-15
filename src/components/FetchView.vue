<script setup>
  import { computed } from "vue";

  import FailureNotice from "./FailureNotice.vue";
  import FormatList from "./FormatList.vue";
  import Icon from "./Icon.vue";
  import MediaPreview from "./MediaPreview.vue";
  import UrlBar from "./UrlBar.vue";

  import { bestPlayable, formatBytes, qualityLabel, totalSizeOf } from "@/media/format.js";
  import { useDownloadStore } from "@/stores/downloads.js";
  import { useResolveStore } from "@/stores/resolve.js";
  import { useSessionStore } from "@/stores/session.js";

  const resolve = useResolveStore();
  const downloads = useDownloadStore();
  const session = useSessionStore();

  const playableTrack = computed(() => {
    const selected = resolve.selectedFormat;

    if (selected?.playable) {
      return selected;
    }

    return bestPlayable(resolve.media?.formats || []);
  });

  const downloadSummary = computed(() => {
    const track = resolve.selectedFormat;

    if (!track) {
      return null;
    }

    const size = formatBytes(totalSizeOf(track, resolve.pairedAudioFormat));

    return [qualityLabel(track), track.ext.toUpperCase(), size].filter(Boolean).join(" · ");
  });

  function download() {
    if (!resolve.selectedFormat) {
      return;
    }

    downloads.start({
      media: resolve.media,
      track: resolve.selectedFormat,
      audioTrack: resolve.pairedAudioFormat
    });
  }
</script>

<template>
  <div class="flex h-full flex-col">
    <div class="shrink-0 space-y-3 px-4 pt-4 pb-3">
      <UrlBar />

      <div
        v-if="session.status === 'ready' && !session.hasYtDlp"
        role="alert"
        class="rounded-lg bg-warning/10 px-3 py-2.5 text-sm text-warning"
      >
        <p class="font-medium">yt-dlp is not installed.</p>
        <p class="mt-1 text-xs opacity-80">
          FetchTube cannot read any link without it. In Termux run
          <code class="rounded bg-base-300 px-1 py-0.5 text-base-content">pkg install yt-dlp</code>
          and reopen this app.
        </p>
      </div>

      <FailureNotice v-else-if="session.failure" :failure="session.failure" />
    </div>

    <div class="scroll-area flex-1 px-4 pb-4">
      <p
        v-if="resolve.status === 'empty'"
        class="mt-16 text-center text-sm text-base-content/50"
      >
        Paste a link to see what it holds.
      </p>

      <div v-else-if="resolve.status === 'resolving'" class="mt-16 flex flex-col items-center gap-3">
        <span class="loading loading-spinner loading-lg text-primary" />
        <p class="text-sm text-base-content/60">Reading the link…</p>
      </div>

      <FailureNotice v-else-if="resolve.status === 'failed'" :failure="resolve.failure" />

      <div v-else-if="resolve.media" class="space-y-5">
        <MediaPreview :media="resolve.media" :playable-track="playableTrack" />

        <p
          v-if="resolve.media.isLive"
          class="rounded-lg bg-warning/10 px-3 py-2 text-xs text-warning"
        >
          This is a live stream. Downloading it captures only what has aired so far.
        </p>

        <FormatList :formats="resolve.media.formats" />
      </div>
    </div>

    <div
      v-if="resolve.media"
      class="shrink-0 border-t border-base-300 bg-base-100 px-4 py-3"
    >
      <FailureNotice v-if="downloads.failure" :failure="downloads.failure" class="mb-3" />

      <button
        type="button"
        class="btn btn-primary w-full"
        :disabled="!resolve.selectedFormat"
        @click="download"
      >
        <Icon name="download" />
        <span class="truncate">{{ downloadSummary || "Choose a format" }}</span>
      </button>
    </div>
  </div>
</template>

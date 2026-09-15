<script setup>
import { computed } from "vue";
import { useResolveStore } from "@/stores/resolve.js";
import { useDownloadStore } from "@/stores/downloads.js";
import { formatDuration } from "@/media/format.js";
import FormatList from "./FormatList.vue";
import Player from "./Player.vue";

const resolve = useResolveStore();
const downloads = useDownloadStore();

const media = computed(() => resolve.media);
const playFormat = computed(() => {
  if (resolve.selectedFormat?.playable) {
    return resolve.selectedFormat;
  }
  return resolve.playableFormat;
});

function download() {
  if (!resolve.selectedFormat) return;
  downloads.start({
    url: media.value.originalUrl,
    format: resolve.selectedFormat,
    title: media.value.title
  });
}
</script>

<template>
  <article v-if="media" class="result">
    <header>
      <img
        v-if="media.thumbnail"
        class="thumb"
        :src="media.thumbnail"
        alt=""
      />
      <div class="head">
        <h2>{{ media.title }}</h2>
        <p class="muted">
          <span v-if="media.uploader">{{ media.uploader }}</span>
          <span v-if="formatDuration(media.duration)">{{ formatDuration(media.duration) }}</span>
          <span v-if="media.extractor">{{ media.extractor }}</span>
        </p>
      </div>
    </header>

    <Player :format="playFormat" :title="media.title" />

    <div class="actions">
      <button
        type="button"
        class="btn btn-primary"
        :disabled="!resolve.selectedFormat"
        @click="download"
      >
        Download selected
      </button>
      <p v-if="resolve.selectedFormat" class="muted">
        {{ resolve.selectedFormat.id }}
        · {{ resolve.selectedFormat.kind }}
        · {{ resolve.selectedFormat.ext }}
      </p>
    </div>

    <FormatList
      :formats="media.formats"
      :selected-id="resolve.selectedFormatId"
      @select="resolve.selectFormat"
    />
  </article>
</template>

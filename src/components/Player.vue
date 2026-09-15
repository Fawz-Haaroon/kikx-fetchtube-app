<script setup>
import { computed, ref, watch } from "vue";

const props = defineProps({
  format: { type: Object, default: null },
  title: { type: String, default: "" }
});

const failed = ref(false);
const src = computed(() => (props.format?.playable ? props.format.url : null));

watch(src, () => {
  failed.value = false;
});
</script>

<template>
  <div class="player">
    <video
      v-if="src && !failed"
      :key="src"
      controls
      playsinline
      preload="metadata"
      :title="title"
      @error="failed = true"
    >
      <source :src="src" />
    </video>
    <p v-else-if="failed" class="muted">
      This URL could not be played in the browser. Download a format instead.
    </p>
    <p v-else class="muted">
      No browser-playable file in this result. Choose a format and download it.
    </p>
  </div>
</template>

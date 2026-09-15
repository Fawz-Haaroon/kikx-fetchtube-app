<script setup>
  import { computed, ref, watch } from "vue";

  import Icon from "./Icon.vue";
  import { formatDuration } from "@/media/format.js";

  const props = defineProps({
    media: { type: Object, required: true },
    playableTrack: { type: Object, default: null }
  });

  const playing = ref(false);
  const playbackFailed = ref(false);

  const duration = computed(() => formatDuration(props.media.durationSeconds));

  watch(
    () => props.media.requestedUrl,
    () => {
      playing.value = false;
      playbackFailed.value = false;
    }
  );
</script>

<template>
  <section class="space-y-3">
    <div class="relative aspect-video rounded-xl overflow-hidden bg-base-300">
      <video
        v-if="playing && playableTrack && !playbackFailed"
        :key="playableTrack.id"
        :src="playableTrack.url"
        class="h-full w-full"
        controls
        autoplay
        playsinline
        preload="metadata"
        @error="playbackFailed = true"
      />

      <template v-else>
        <img
          v-if="media.thumbnail"
          :src="media.thumbnail"
          alt=""
          class="h-full w-full object-cover"
          referrerpolicy="no-referrer"
        />

        <button
          v-if="playableTrack && !playbackFailed"
          type="button"
          class="absolute inset-0 grid place-items-center bg-black/35"
          aria-label="Play preview"
          @click="playing = true"
        >
          <span class="btn btn-circle btn-primary btn-lg pointer-events-none">
            <Icon name="play" :size="28" />
          </span>
        </button>

        <p
          v-else
          class="absolute inset-x-0 bottom-0 bg-base-100/85 px-3 py-2 text-xs text-base-content/70"
        >
          {{
            playbackFailed
              ? "The stream would not play here. Download it instead."
              : "No stream this player can open directly. Download a format to watch it."
          }}
        </p>

        <span
          v-if="duration"
          class="absolute right-2 top-2 rounded bg-black/70 px-1.5 py-0.5 text-xs text-white tabular-nums"
        >
          {{ duration }}
        </span>
      </template>
    </div>

    <div>
      <h2 class="font-semibold leading-snug line-clamp-2 break-words">{{ media.title }}</h2>
      <p class="mt-0.5 text-xs text-base-content/60 break-words">
        <span v-if="media.uploader" class="meta-dot">{{ media.uploader }}</span>
        <span v-if="media.source" class="meta-dot">{{ media.source }}</span>
        <span class="meta-dot">{{ media.formats.length }} formats</span>
      </p>
    </div>
  </section>
</template>

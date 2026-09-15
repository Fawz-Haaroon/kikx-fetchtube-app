<script setup>
  import { computed } from "vue";

  import {
    bestAudioFor,
    formatBytes,
    groupFormats,
    needsMerge,
    qualityLabel,
    totalSizeOf
  } from "@/media/format.js";
  import { useResolveStore } from "@/stores/resolve.js";
  import { useSessionStore } from "@/stores/session.js";

  const props = defineProps({
    formats: { type: Array, required: true }
  });

  const resolve = useResolveStore();
  const session = useSessionStore();

  const groups = computed(() => groupFormats(props.formats));

  // Each row states its own total, so a video-only row shows the size it will
  // actually reach once audio is merged in rather than the selected row's.
  function sizeFor(track) {
    const paired = needsMerge(track) ? bestAudioFor(props.formats) : null;

    return formatBytes(totalSizeOf(track, paired)) || "Size not reported";
  }

  function codecFor(track) {
    if (!track.codecsKnown) {
      return "codecs not reported";
    }

    return [track.videoCodec, track.audioCodec].filter(Boolean).join(" / ");
  }

  /** A video-only track needs ffmpeg to be merged with audio. Saying so on the
   *  row is better than letting the download fail later. */
  function blockedReason(track) {
    if (track.kind !== "video") {
      return null;
    }

    if (!session.hasFfmpeg) {
      return "needs ffmpeg";
    }

    return props.formats.some(item => item.kind === "audio") ? null : "no audio track to merge";
  }
</script>

<template>
  <div class="space-y-4">
    <section v-for="group in groups" :key="group.kind" class="space-y-1.5">
      <h3 class="text-xs font-semibold uppercase tracking-wide text-base-content/50">
        {{ group.label }}
      </h3>

      <button
        v-for="track in group.tracks"
        :key="track.id"
        type="button"
        class="track-row"
        :aria-pressed="track.id === resolve.selectedFormatId"
        :disabled="Boolean(blockedReason(track))"
        :class="{ 'opacity-40': Boolean(blockedReason(track)) }"
        @click="resolve.select(track.id)"
      >
        <span class="font-semibold tabular-nums w-16 shrink-0">{{ qualityLabel(track) }}</span>

        <span class="min-w-0 flex-1">
          <span class="block text-sm truncate">
            {{ track.ext.toUpperCase() }}
            <span class="text-base-content/50">{{ codecFor(track) }}</span>
          </span>
          <span class="block text-xs text-base-content/50">
            {{ blockedReason(track) || sizeFor(track) }}
          </span>
        </span>

        <span v-if="track.playable" class="badge badge-ghost badge-sm shrink-0">playable</span>
      </button>
    </section>
  </div>
</template>

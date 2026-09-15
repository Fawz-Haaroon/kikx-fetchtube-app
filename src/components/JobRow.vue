<script setup>
  import { computed } from "vue";

  import Icon from "./Icon.vue";
  import { describe } from "@/extractor/messages.js";
  import { formatBytes, formatEta, formatRate } from "@/media/format.js";

  const props = defineProps({
    job: { type: Object, required: true }
  });

  const emit = defineEmits(["cancel", "dismiss"]);

  const ACTIVE = new Set(["queued", "downloading", "merging", "storing"]);

  const isActive = computed(() => ACTIVE.has(props.job.state));

  const STATE_TEXT = {
    queued: "Waiting for a free slot",
    merging: "Combining video and audio",
    storing: "Saving",
    cancelled: "Cancelled",
    completed: "Saved"
  };

  /** Only real numbers appear here. yt-dlp reports speed and remaining time
   *  once it has something to report, and nothing is shown until then. */
  const statusLine = computed(() => {
    const job = props.job;

    if (job.state === "failed") {
      return describe(job.error);
    }

    if (job.state === "completed") {
      return formatBytes(job.sizeBytes) || STATE_TEXT.completed;
    }

    if (job.state !== "downloading") {
      return STATE_TEXT[job.state];
    }

    const parts = [
      job.totalBytes
        ? `${formatBytes(job.downloadedBytes)} of ${formatBytes(job.totalBytes)}`
        : formatBytes(job.downloadedBytes),
      formatRate(job.speedBytesPerSecond),
      formatEta(job.etaSeconds)
    ];

    return parts.filter(Boolean).join(" · ") || "Starting";
  });
</script>

<template>
  <li class="rounded-xl bg-base-200/60 px-3 py-3">
    <div class="flex items-start gap-3">
      <div class="min-w-0 flex-1">
        <p class="text-sm font-medium line-clamp-2 break-words">{{ job.title }}</p>
        <p class="mt-0.5 text-xs text-base-content/50 break-words">{{ job.formatLabel }}</p>
      </div>

      <button
        v-if="isActive"
        type="button"
        class="btn btn-ghost btn-sm btn-square"
        aria-label="Cancel download"
        @click="emit('cancel', job.id)"
      >
        <Icon name="close" :size="16" />
      </button>

      <button
        v-else
        type="button"
        class="btn btn-ghost btn-sm btn-square"
        aria-label="Remove from list"
        @click="emit('dismiss', job.id)"
      >
        <Icon name="close" :size="16" />
      </button>
    </div>

    <progress
      v-if="isActive"
      class="progress progress-primary mt-2.5 h-1.5 w-full"
      :value="job.percent ?? undefined"
      max="100"
    />

    <p
      class="mt-1.5 text-xs tabular-nums break-words"
      :class="job.state === 'failed' ? 'text-error' : 'text-base-content/60'"
    >
      <span v-if="job.percent != null && isActive" class="font-medium">
        {{ Math.round(job.percent) }}% ·
      </span>
      {{ statusLine }}
    </p>

    <slot name="actions" />
  </li>
</template>

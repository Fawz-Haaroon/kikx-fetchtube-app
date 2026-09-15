<script setup>
import { useDownloadStore } from "@/stores/downloads.js";
import { formatSize } from "@/media/format.js";
import { messageForError } from "@/media/errors.js";

const downloads = useDownloadStore();

function progressText(item) {
  if (item.status === "completed") {
    return item.filename || "Saved";
  }
  if (item.percent != null) {
    const size = item.total ? ` of ${formatSize(item.total)}` : "";
    const speed = item.speed ? ` · ${item.speed}` : "";
    return `${Math.round(item.percent)}%${size}${speed}`;
  }
  if (item.downloaded != null) {
    return `${formatSize(item.downloaded)} downloaded`;
  }
  return item.status;
}

function canCancel(item) {
  return item.status === "starting" || item.status === "downloading";
}
</script>

<template>
  <section v-if="downloads.items.length" class="downloads">
    <h2>Downloads</h2>
    <ul>
      <li v-for="item in downloads.items" :key="item.id">
        <div>
          <p class="title">{{ item.title }}</p>
          <p class="muted">{{ item.formatLabel }} · {{ progressText(item) }}</p>
          <p v-if="item.status === 'failed'" class="error">
            {{ messageForError(item.error) }}
          </p>
          <p v-if="item.path" class="muted path">{{ item.path }}</p>
        </div>
        <button
          v-if="canCancel(item)"
          type="button"
          class="btn btn-ghost"
          @click="downloads.cancel(item.id)"
        >
          Cancel
        </button>
      </li>
    </ul>
  </section>
</template>

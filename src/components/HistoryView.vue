<script setup>
  import Icon from "./Icon.vue";
  import { formatDuration } from "@/media/format.js";
  import { useHistoryStore } from "@/stores/history.js";
  import { useResolveStore } from "@/stores/resolve.js";

  const emit = defineEmits(["opened"]);

  const history = useHistoryStore();
  const resolve = useResolveStore();

  function open(entry) {
    emit("opened");
    resolve.resolve(entry.url);
  }
</script>

<template>
  <div class="scroll-area h-full px-4 py-4">
    <p v-if="!history.available" class="mt-16 text-center text-sm text-base-content/50">
      History is stored by KIKX and is unavailable outside it.
    </p>

    <p
      v-else-if="history.entries.length === 0"
      class="mt-16 text-center text-sm text-base-content/50"
    >
      Links you resolve appear here.
    </p>

    <template v-else>
      <div class="mb-2 flex items-center justify-between">
        <h2 class="text-xs font-semibold uppercase tracking-wide text-base-content/50">
          Recent links
        </h2>
        <button type="button" class="btn btn-ghost btn-sm" @click="history.clear">Clear</button>
      </div>

      <ul class="space-y-2">
        <li
          v-for="entry in history.entries"
          :key="entry.url"
          class="flex items-center gap-3 rounded-xl bg-base-200/60 pr-2"
        >
          <button
            type="button"
            class="flex min-w-0 flex-1 items-center gap-3 p-2 text-left"
            @click="open(entry)"
          >
            <span
              class="grid h-12 w-20 shrink-0 place-items-center overflow-hidden rounded-lg bg-base-300"
            >
              <img
                v-if="entry.thumbnail"
                :src="entry.thumbnail"
                alt=""
                class="h-full w-full object-cover"
                referrerpolicy="no-referrer"
              />
              <Icon v-else name="clock" :size="18" class="opacity-40" />
            </span>

            <span class="min-w-0 flex-1">
              <span class="block text-sm line-clamp-2 break-words">{{ entry.title }}</span>
              <span class="mt-0.5 block text-xs text-base-content/50">
                <span v-if="entry.uploader" class="meta-dot">{{ entry.uploader }}</span>
                <span v-if="formatDuration(entry.durationSeconds)" class="meta-dot">
                  {{ formatDuration(entry.durationSeconds) }}
                </span>
              </span>
            </span>
          </button>

          <button
            type="button"
            class="btn btn-ghost btn-sm btn-square"
            aria-label="Remove from history"
            @click="history.remove(entry.url)"
          >
            <Icon name="close" :size="16" />
          </button>
        </li>
      </ul>
    </template>
  </div>
</template>

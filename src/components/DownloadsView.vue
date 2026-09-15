<script setup>
  import { computed, ref } from "vue";

  import FailureNotice from "./FailureNotice.vue";
  import Icon from "./Icon.vue";
  import JobRow from "./JobRow.vue";

  import { formatBytes } from "@/media/format.js";
  import { useDownloadStore } from "@/stores/downloads.js";
  import { useSessionStore } from "@/stores/session.js";

  const downloads = useDownloadStore();
  const session = useSessionStore();

  const playing = ref(null);

  /** A stored file the app can play back from KIKX app storage. */
  function localUrl(relativePath) {
    return session.localUrlFor(relativePath);
  }

  async function saveToDevice(entry) {
    const url = await downloads.deviceUrlFor(entry.relativePath);

    if (!url) {
      return;
    }

    // The iframe carries allow-downloads (app.json), and the fs serve route
    // sends the file as an attachment, so this hands it to the browser.
    const link = document.createElement("a");

    link.href = url;
    link.download = entry.filename;
    document.body.append(link);
    link.click();
    link.remove();
  }

  async function removeStored(entry) {
    if (playing.value === entry.relativePath) {
      playing.value = null;
    }

    await downloads.remove(entry.filename);
  }

  const empty = computed(
    () => downloads.jobs.length === 0 && downloads.library.length === 0
  );
</script>

<template>
  <div class="scroll-area h-full px-4 py-4">
    <FailureNotice v-if="downloads.failure" :failure="downloads.failure" class="mb-4" />

    <p v-if="empty" class="mt-16 text-center text-sm text-base-content/50">
      Nothing downloaded yet.
    </p>

    <section v-if="downloads.jobs.length" class="mb-6">
      <h2 class="mb-2 text-xs font-semibold uppercase tracking-wide text-base-content/50">
        Transfers
      </h2>

      <ul class="space-y-2">
        <JobRow
          v-for="job in downloads.jobs"
          :key="job.id"
          :job="job"
          @cancel="downloads.cancel"
          @dismiss="downloads.dismiss"
        />
      </ul>
    </section>

    <section v-if="downloads.library.length">
      <h2 class="mb-2 text-xs font-semibold uppercase tracking-wide text-base-content/50">
        Stored files
      </h2>

      <ul class="space-y-2">
        <li
          v-for="entry in downloads.library"
          :key="entry.relativePath"
          class="rounded-xl bg-base-200/60 px-3 py-3"
        >
          <p class="text-sm font-medium break-all line-clamp-2">{{ entry.filename }}</p>
          <p class="mt-0.5 text-xs text-base-content/50">{{ formatBytes(entry.sizeBytes) }}</p>

          <video
            v-if="playing === entry.relativePath && localUrl(entry.relativePath)"
            :src="localUrl(entry.relativePath)"
            class="mt-2.5 w-full rounded-lg bg-black"
            controls
            autoplay
            playsinline
          />

          <div class="mt-2.5 flex flex-wrap gap-2">
            <button
              v-if="localUrl(entry.relativePath) && playing !== entry.relativePath"
              type="button"
              class="btn btn-sm btn-ghost"
              @click="playing = entry.relativePath"
            >
              <Icon name="play" :size="16" /> Play
            </button>

            <button
              v-if="session.canSaveToDevice"
              type="button"
              class="btn btn-sm btn-ghost"
              @click="saveToDevice(entry)"
            >
              <Icon name="save" :size="16" /> Save to device
            </button>

            <button
              type="button"
              class="btn btn-sm btn-ghost text-error"
              @click="removeStored(entry)"
            >
              <Icon name="trash" :size="16" /> Delete
            </button>
          </div>
        </li>
      </ul>
    </section>
  </div>
</template>

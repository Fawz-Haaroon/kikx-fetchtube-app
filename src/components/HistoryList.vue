<script setup>
import { useHistoryStore } from "@/stores/history.js";
import { useResolveStore } from "@/stores/resolve.js";
import { formatDuration } from "@/media/format.js";

const history = useHistoryStore();
const resolve = useResolveStore();

function open(entry) {
  resolve.resolve(entry.url);
}
</script>

<template>
  <section v-if="history.entries.length" class="history">
    <div class="row">
      <h2>History</h2>
      <button type="button" class="btn btn-ghost" @click="history.clear">
        Clear
      </button>
    </div>
    <ul>
      <li v-for="entry in history.entries" :key="entry.url + entry.at">
        <button type="button" class="history-item" @click="open(entry)">
          <img v-if="entry.thumbnail" :src="entry.thumbnail" alt="" />
          <span>
            <strong>{{ entry.title }}</strong>
            <small class="muted">
              {{ formatDuration(entry.duration) || "—" }}
            </small>
          </span>
        </button>
      </li>
    </ul>
  </section>
</template>

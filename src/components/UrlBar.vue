<script setup>
import { ref } from "vue";
import { useResolveStore } from "@/stores/resolve.js";

const store = useResolveStore();
const localUrl = ref(store.url);

function submit() {
  store.resolve(localUrl.value);
}
</script>

<template>
  <form class="url-bar" @submit.prevent="submit">
    <label class="sr-only" for="media-url">Media URL</label>
    <input
      id="media-url"
      v-model="localUrl"
      type="url"
      inputmode="url"
      autocomplete="url"
      placeholder="Paste a media URL"
      :disabled="store.status === 'resolving'"
    />
    <button
      type="submit"
      class="btn btn-primary"
      :disabled="store.status === 'resolving' || !localUrl.trim()"
    >
      {{ store.status === "resolving" ? "Resolving…" : "Resolve" }}
    </button>
  </form>
</template>

<script setup>
  import { ref, watch } from "vue";

  import Icon from "./Icon.vue";
  import { useResolveStore } from "@/stores/resolve.js";

  const resolve = useResolveStore();
  const draft = ref(resolve.url);

  watch(
    () => resolve.url,
    value => {
      draft.value = value;
    }
  );

  function submit() {
    const url = draft.value.trim();

    if (url) {
      resolve.resolve(url);
    }
  }
</script>

<template>
  <form class="flex gap-2" @submit.prevent="submit">
    <label class="sr-only" for="media-url">Media link</label>
    <input
      id="media-url"
      v-model="draft"
      type="text"
      inputmode="url"
      spellcheck="false"
      autocomplete="off"
      autocapitalize="off"
      placeholder="Paste a media link"
      class="input input-bordered flex-1 min-w-0"
      :disabled="resolve.status === 'resolving'"
    />
    <button
      type="submit"
      class="btn btn-primary btn-square"
      :disabled="resolve.status === 'resolving' || !draft.trim()"
      :aria-label="resolve.status === 'resolving' ? 'Resolving' : 'Resolve link'"
    >
      <span v-if="resolve.status === 'resolving'" class="loading loading-spinner loading-sm" />
      <Icon v-else name="search" />
    </button>
  </form>
</template>

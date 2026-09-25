<script setup>
  import { nextTick, ref, watch } from "vue";

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

  // v-model syncs from the input event, which every browser fires for a
  // paste. This is a defensive backstop, not a fix for a known gap: if a
  // paste ever lands in the field without one, the button would otherwise
  // stay disabled with no visible reason why.
  function resyncAfterPaste(event) {
    nextTick(() => {
      draft.value = event.target.value;
    });
  }
</script>

<template>
  <div class="flex gap-2">
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
      @keydown.enter="submit"
      @paste="resyncAfterPaste"
    />
    <button
      type="button"
      class="btn btn-primary btn-square"
      :disabled="resolve.status === 'resolving' || !draft.trim()"
      :aria-label="resolve.status === 'resolving' ? 'Resolving' : 'Resolve link'"
      @click="submit"
    >
      <span v-if="resolve.status === 'resolving'" class="loading loading-spinner loading-sm" />
      <Icon v-else name="search" />
    </button>
  </div>
</template>

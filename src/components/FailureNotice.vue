<script setup>
  import Icon from "./Icon.vue";

  defineProps({
    failure: { type: Object, required: true }
  });
</script>

<template>
  <div role="alert" class="rounded-lg bg-error/10 px-3 py-2.5 text-sm text-error flex gap-2.5">
    <Icon name="warning" :size="18" class="mt-0.5" />
    <span class="min-w-0">
      <span class="block">{{ failure.message }}</span>
      <span v-if="failure.detail" class="mt-0.5 block break-words text-xs opacity-75">
        {{ failure.detail }}
      </span>
    </span>
  </div>
</template>

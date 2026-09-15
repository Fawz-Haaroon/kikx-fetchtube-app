<script setup>
import { computed } from "vue";
import { formatLabel, formatSize, kindLabel } from "@/media/format.js";

const props = defineProps({
  formats: { type: Array, required: true },
  selectedId: { type: String, default: null }
});

const emit = defineEmits(["select"]);

const groups = computed(() => {
  const order = ["muxed", "video", "audio"];
  return order
    .map(kind => ({
      kind,
      label: kindLabel(kind),
      items: props.formats.filter(item => item.kind === kind)
    }))
    .filter(group => group.items.length);
});
</script>

<template>
  <div class="formats">
    <section v-for="group in groups" :key="group.kind">
      <h3>{{ group.label }}</h3>
      <ul>
        <li v-for="fmt in group.items" :key="fmt.id">
          <button
            type="button"
            class="format"
            :class="{ selected: fmt.id === selectedId }"
            @click="emit('select', fmt.id)"
          >
            <span class="label">{{ formatLabel(fmt) }}</span>
            <span class="meta">
              <span v-if="formatSize(fmt.filesize)">{{ formatSize(fmt.filesize) }}</span>
              <span v-if="fmt.playable">playable</span>
            </span>
          </button>
        </li>
      </ul>
    </section>
  </div>
</template>

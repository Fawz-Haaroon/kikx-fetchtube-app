<script setup>
  // Inline paths keep the package free of an icon dependency for the eight
  // glyphs this app uses.
  const PATHS = {
    search: "M10 3a7 7 0 105.29 11.71l4 4 1.42-1.42-4-4A7 7 0 0010 3zm0 2a5 5 0 110 10 5 5 0 010-10z",
    download: "M12 3v10.17l3.59-3.58L17 11l-5 5-5-5 1.41-1.41L12 13.17V3zM5 19h14v2H5z",
    clock: "M12 2a10 10 0 100 20 10 10 0 000-20zm0 2a8 8 0 110 16 8 8 0 010-16zm-1 3v6l5 3 .9-1.5-4.4-2.6V7z",
    play: "M8 5v14l11-7z",
    close: "M6.4 5 5 6.4 10.6 12 5 17.6 6.4 19 12 13.4 17.6 19 19 17.6 13.4 12 19 6.4 17.6 5 12 10.6z",
    trash: "M9 3h6l1 2h4v2H4V5h4zM6 9h12l-1 12H7zm3 2v8h2v-8zm4 0v8h2v-8z",
    save: "M5 3h11l3 3v15H5zm2 2v4h8V5zm0 9v5h10v-5z",
    warning: "M12 2 1 21h22zm0 5 7.5 12h-15zM11 10v5h2v-5zm0 6v2h2v-2z"
  };

  defineProps({
    name: { type: String, required: true },
    size: { type: Number, default: 20 }
  });
</script>

<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="currentColor"
    aria-hidden="true"
    class="shrink-0"
  >
    <path :d="PATHS[name]" />
  </svg>
</template>

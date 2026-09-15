import { defineStore } from "pinia";
import { getExtractor } from "@/services/extractor.js";
import { errorFromUnknown } from "@/media/errors.js";
import { looksLikeUrl, pickDefaultFormat, pickPlayableFormat } from "@/media/format.js";
import { useHistoryStore } from "./history.js";

export const useResolveStore = defineStore("resolve", {
  state: () => ({
    url: "",
    status: "idle",
    media: null,
    error: null,
    selectedFormatId: null
  }),
  getters: {
    selectedFormat(state) {
      return state.media?.formats.find(item => item.id === state.selectedFormatId) || null;
    },
    playableFormat(state) {
      return pickPlayableFormat(state.media?.formats || []);
    }
  },
  actions: {
    selectFormat(id) {
      this.selectedFormatId = id;
    },
    clearError() {
      this.error = null;
    },
    async resolve(rawUrl) {
      const url = rawUrl.trim();
      this.url = url;
      if (!looksLikeUrl(url)) {
        this.status = "error";
        this.error = { code: "invalid_url" };
        this.media = null;
        return;
      }

      this.status = "resolving";
      this.error = null;
      this.media = null;
      this.selectedFormatId = null;

      try {
        const extractor = await getExtractor();
        const media = await extractor.resolve(url);
        this.media = media;
        this.status = "ready";
        const fallback = pickDefaultFormat(media.formats);
        this.selectedFormatId = fallback?.id || null;
        await useHistoryStore().remember(media, url);
      } catch (error) {
        this.status = "error";
        this.error = errorFromUnknown(error);
      }
    }
  }
});

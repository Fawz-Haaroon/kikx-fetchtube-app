import { defineStore } from "pinia";

import { codeOf, describe, detailOf } from "@/extractor/messages.js";
import { bestAudioFor, defaultTrack, looksLikeUrl } from "@/media/format.js";
import { extractor } from "./session.js";
import { useHistoryStore } from "./history.js";

export const useResolveStore = defineStore("resolve", {
  state: () => ({
    url: "",
    status: "empty",
    media: null,
    selectedFormatId: null,
    failure: null
  }),

  getters: {
    selectedFormat(state) {
      return state.media?.formats.find(track => track.id === state.selectedFormatId) || null;
    },

    /** The audio track that would be merged with the selection. Null unless the
     *  selection is video only. */
    pairedAudioFormat() {
      const track = this.selectedFormat;

      if (!track || track.kind !== "video") {
        return null;
      }

      return bestAudioFor(this.media?.formats || []);
    }
  },

  actions: {
    select(formatId) {
      this.selectedFormatId = formatId;
    },

    clear() {
      this.url = "";
      this.status = "empty";
      this.media = null;
      this.selectedFormatId = null;
      this.failure = null;
    },

    async resolve(rawUrl) {
      const url = String(rawUrl || "").trim();

      this.url = url;
      this.media = null;
      this.selectedFormatId = null;
      this.failure = null;

      if (!looksLikeUrl(url)) {
        this.status = "failed";
        this.failure = { code: "invalid_url", message: describe({ code: "invalid_url" }), detail: null };

        return;
      }

      this.status = "resolving";

      try {
        const media = await extractor().resolve(url);

        this.media = media;
        this.selectedFormatId = defaultTrack(media.formats)?.id || null;
        this.status = "resolved";

        await useHistoryStore().remember(media);
      } catch (error) {
        this.status = "failed";
        this.failure = {
          code: codeOf(error),
          message: describe(error),
          detail: detailOf(error)
        };
      }
    }
  }
});

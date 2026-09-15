import { defineStore } from "pinia";
import { historyEntryFromMedia, loadHistory, saveHistory } from "@/services/history.js";

export const useHistoryStore = defineStore("history", {
  state: () => ({
    entries: []
  }),
  actions: {
    async hydrate() {
      this.entries = await loadHistory();
    },
    async remember(media, url) {
      const entry = historyEntryFromMedia(media, url);
      this.entries = [
        entry,
        ...this.entries.filter(item => item.url !== url)
      ];
      this.entries = await saveHistory(this.entries);
    },
    async clear() {
      this.entries = await saveHistory([]);
    }
  }
});

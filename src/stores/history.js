import { defineStore } from "pinia";

import { runtime } from "./session.js";

const KV_KEY = "history";
const MAX_ENTRIES = 50;

/** KIKX's KV get returns an envelope, not the stored value
 *  (kikx/services/kv/main.py returns { key, exists, value }). */
async function readStored() {
  const kv = runtime()?.kv;

  if (!kv) {
    return [];
  }

  try {
    const envelope = await kv.get(KV_KEY);

    return Array.isArray(envelope?.value) ? envelope.value : [];
  } catch {
    return [];
  }
}

async function writeStored(entries) {
  const kv = runtime()?.kv;

  if (!kv) {
    return;
  }

  // KV persists on set (Collection.set saves immediately), so there is no
  // separate save call here.
  await kv.set(KV_KEY, entries);
}

export const useHistoryStore = defineStore("history", {
  state: () => ({
    entries: [],
    available: false
  }),

  actions: {
    async load() {
      this.available = Boolean(runtime()?.kv);
      this.entries = await readStored();
    },

    async remember(media) {
      if (!this.available) {
        return;
      }

      const entry = {
        url: media.requestedUrl,
        title: media.title,
        uploader: media.uploader || null,
        thumbnail: media.thumbnail || null,
        durationSeconds: media.durationSeconds ?? null,
        source: media.source || null,
        at: Date.now()
      };

      this.entries = [entry, ...this.entries.filter(item => item.url !== entry.url)].slice(
        0,
        MAX_ENTRIES
      );

      await writeStored(this.entries);
    },

    async remove(url) {
      this.entries = this.entries.filter(entry => entry.url !== url);

      await writeStored(this.entries);
    },

    async clear() {
      this.entries = [];

      await writeStored(this.entries);
    }
  }
});

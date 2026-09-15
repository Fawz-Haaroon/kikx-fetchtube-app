import { getKv, hasKikx } from "./runtime.js";

const KEY = "history";
const LOCAL_KEY = "fetchtube-history";
const LIMIT = 40;

function readLocal() {
  try {
    const raw = localStorage.getItem(LOCAL_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function writeLocal(entries) {
  localStorage.setItem(LOCAL_KEY, JSON.stringify(entries));
}

export async function loadHistory() {
  if (hasKikx()) {
    try {
      const data = await getKv().get(KEY);
      return Array.isArray(data) ? data : [];
    } catch {
      return [];
    }
  }
  return readLocal();
}

export async function saveHistory(entries) {
  const trimmed = entries.slice(0, LIMIT);
  if (hasKikx()) {
    await getKv().set(KEY, trimmed);
    try {
      await getKv().save();
    } catch {
      // Some KV backends persist on set.
    }
    return trimmed;
  }
  writeLocal(trimmed);
  return trimmed;
}

export function historyEntryFromMedia(media, url) {
  return {
    url,
    title: media.title,
    thumbnail: media.thumbnail || null,
    duration: media.duration ?? null,
    at: Date.now()
  };
}

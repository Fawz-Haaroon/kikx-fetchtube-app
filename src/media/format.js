/** Presentation helpers over the normalized media the extractor sends.
 *  Nothing here talks to KIKX or to yt-dlp. */

export function formatDuration(seconds) {
  if (seconds == null || !Number.isFinite(Number(seconds))) {
    return null;
  }

  const total = Math.max(0, Math.round(Number(seconds)));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const rest = total % 60;

  const pad = value => String(value).padStart(2, "0");

  return hours > 0 ? `${hours}:${pad(minutes)}:${pad(rest)}` : `${minutes}:${pad(rest)}`;
}

export function formatBytes(bytes) {
  if (bytes == null || !Number.isFinite(Number(bytes))) {
    return null;
  }

  const units = ["B", "KB", "MB", "GB", "TB"];

  let size = Number(bytes);
  let unit = 0;

  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }

  return `${size.toFixed(size >= 10 || unit === 0 ? 0 : 1)} ${units[unit]}`;
}

export function formatRate(bytesPerSecond) {
  const readable = formatBytes(bytesPerSecond);

  return readable ? `${readable}/s` : null;
}

export function formatEta(seconds) {
  if (seconds == null || !Number.isFinite(Number(seconds))) {
    return null;
  }

  return `${formatDuration(seconds)} left`;
}

export function qualityLabel(track) {
  if (track.kind === "audio") {
    return track.audioBitrateKbps ? `${Math.round(track.audioBitrateKbps)} kbps` : "Audio";
  }

  if (track.height) {
    return `${track.height}p${track.fps && track.fps >= 50 ? Math.round(track.fps) : ""}`;
  }

  return track.resolution || track.ext.toUpperCase();
}

export function kindLabel(kind) {
  if (kind === "muxed") return "Video with audio";
  if (kind === "video") return "Video only";

  return "Audio only";
}

/** Video-only tracks need an audio track merged in. The UI decides the pairing
 *  because it already holds the whole format list; asking the extractor would
 *  mean resolving the link a second time. */
export function bestAudioFor(formats) {
  const audio = formats.filter(track => track.kind === "audio");

  if (audio.length === 0) {
    return null;
  }

  return [...audio].sort(
    (a, b) => (b.audioBitrateKbps || b.bitrateKbps || 0) - (a.audioBitrateKbps || a.bitrateKbps || 0)
  )[0];
}

export function needsMerge(track) {
  return track.kind === "video";
}

/** Estimated size of what will actually land on disk. */
export function totalSizeOf(track, audioTrack) {
  if (!track.sizeBytes) {
    return null;
  }

  if (!needsMerge(track) || !audioTrack?.sizeBytes) {
    return track.sizeBytes;
  }

  return track.sizeBytes + audioTrack.sizeBytes;
}

const KIND_ORDER = ["muxed", "video", "audio"];

export function groupFormats(formats) {
  return KIND_ORDER.map(kind => ({
    kind,
    label: kindLabel(kind),
    tracks: formats.filter(track => track.kind === kind)
  })).filter(group => group.tracks.length > 0);
}

export function defaultTrack(formats) {
  const muxed = formats.filter(track => track.kind === "muxed");

  return (muxed.length > 0 ? muxed : formats)[0] || null;
}

export function bestPlayable(formats) {
  return formats.find(track => track.playable) || null;
}

export function looksLikeUrl(value) {
  try {
    const parsed = new URL(String(value).trim());

    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

export function formatDuration(seconds) {
  if (seconds == null || Number.isNaN(Number(seconds))) {
    return null;
  }
  const total = Math.max(0, Math.round(Number(seconds)));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  }
  return `${minutes}:${String(secs).padStart(2, "0")}`;
}

export function formatSize(bytes) {
  if (bytes == null || Number.isNaN(Number(bytes))) {
    return null;
  }
  const value = Number(bytes);
  const units = ["B", "KB", "MB", "GB"];
  let size = value;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  const digits = size >= 10 || unit === 0 ? 0 : 1;
  return `${size.toFixed(digits)} ${units[unit]}`;
}

export function formatLabel(fmt) {
  if (fmt.kind === "audio") {
    return [fmt.ext, fmt.abr ? `${Math.round(fmt.abr)} kbps` : null, fmt.acodec]
      .filter(Boolean)
      .join(" · ");
  }
  const res = fmt.height ? `${fmt.height}p` : fmt.resolution;
  return [res, fmt.ext, fmt.fps ? `${Math.round(fmt.fps)} fps` : null]
    .filter(Boolean)
    .join(" · ");
}

export function kindLabel(kind) {
  if (kind === "muxed") return "Video + audio";
  if (kind === "video") return "Video only";
  if (kind === "audio") return "Audio only";
  return kind;
}

export function pickDefaultFormat(formats) {
  if (!formats?.length) {
    return null;
  }
  const muxed = formats.filter(f => f.kind === "muxed");
  const pool = muxed.length ? muxed : formats;
  return [...pool].sort(compareFormats)[0];
}

export function pickPlayableFormat(formats) {
  const playable = (formats || []).filter(f => f.playable);
  if (!playable.length) {
    return null;
  }
  return [...playable].sort(compareFormats)[0];
}

function compareFormats(a, b) {
  const height = (b.height || 0) - (a.height || 0);
  if (height !== 0) return height;
  const br = (b.tbr || b.abr || 0) - (a.tbr || a.abr || 0);
  if (br !== 0) return br;
  return (b.filesize || 0) - (a.filesize || 0);
}

export function looksLikeUrl(value) {
  try {
    const parsed = new URL(value.trim());
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

from urllib.parse import urlparse

from errors import ExtractorError


PLAYABLE_EXTENSIONS = frozenset(
  {"mp4", "webm", "ogg", "ogv", "mp3", "wav", "m4a", "aac", "mov"}
)


def require_http_url(value):
  if not isinstance(value, str):
    raise ExtractorError("invalid_url", "A URL string is required.")

  text = value.strip()
  if not text or len(text) > 2048:
    raise ExtractorError("invalid_url", "The URL is empty or too long.")

  parsed = urlparse(text)
  if parsed.scheme not in ("http", "https"):
    raise ExtractorError("invalid_url", "Only http and https URLs are accepted.")
  if not parsed.netloc:
    raise ExtractorError("invalid_url", "The URL is missing a host.")
  if parsed.username or parsed.password:
    raise ExtractorError("invalid_url", "The URL must not contain credentials.")
  return text


def safe_filename(title, ext):
  raw = (title or "media").replace("/", "_").replace("\\", "_")
  cleaned = []
  for ch in raw:
    if ch.isalnum() or ch in " ._-+()[]":
      cleaned.append(ch)
    else:
      cleaned.append("_")
  name = "".join(cleaned).strip(" ._")
  if not name:
    name = "media"
  name = name[:80]
  suffix = (ext or "bin").lstrip(".").lower()
  if not suffix.isalnum() or len(suffix) > 8:
    suffix = "bin"
  return f"{name}.{suffix}"


def _none_codec(value):
  if value is None:
    return None
  text = str(value).strip().lower()
  if text in ("", "none", "null"):
    return None
  return str(value)


def classify_format(raw):
  vcodec = _none_codec(raw.get("vcodec"))
  acodec = _none_codec(raw.get("acodec"))
  if vcodec and acodec:
    return "muxed"
  if vcodec:
    return "video"
  if acodec:
    return "audio"
  return None


def is_browser_playable(fmt):
  if fmt["kind"] not in ("muxed", "audio"):
    return False
  ext = (fmt.get("ext") or "").lower()
  if ext not in PLAYABLE_EXTENSIONS:
    return False
  url = fmt.get("url") or ""
  parsed = urlparse(url)
  if parsed.scheme not in ("http", "https"):
    return False
  protocol = (fmt.get("protocol") or "").lower()
  if "m3u8" in protocol or "dash" in protocol or "rtmp" in protocol:
    return False
  return True


def normalize_format(raw):
  kind = classify_format(raw)
  if kind is None:
    return None

  format_id = str(raw.get("format_id") or "")
  if not format_id:
    return None

  width = raw.get("width")
  height = raw.get("height")
  resolution = raw.get("resolution")
  if not resolution and width and height:
    resolution = f"{width}x{height}"

  fmt = {
    "id": format_id,
    "kind": kind,
    "ext": raw.get("ext"),
    "resolution": resolution,
    "width": width,
    "height": height,
    "fps": raw.get("fps"),
    "vcodec": _none_codec(raw.get("vcodec")),
    "acodec": _none_codec(raw.get("acodec")),
    "filesize": raw.get("filesize") or raw.get("filesize_approx"),
    "tbr": raw.get("tbr"),
    "abr": raw.get("abr"),
    "vbr": raw.get("vbr"),
    "protocol": raw.get("protocol"),
    "note": raw.get("format_note") or raw.get("format"),
    "url": raw.get("url"),
  }
  fmt["playable"] = is_browser_playable(fmt)
  return fmt


def normalize_media(raw, original_url):
  formats = []
  for item in raw.get("formats") or []:
    fmt = normalize_format(item)
    if fmt is not None:
      formats.append(fmt)

  requested = raw.get("requested_formats")
  if not formats and requested:
    for item in requested:
      fmt = normalize_format(item)
      if fmt is not None:
        formats.append(fmt)

  duration = raw.get("duration")
  if duration is not None:
    try:
      duration = float(duration)
    except (TypeError, ValueError):
      duration = None

  return {
    "originalUrl": original_url,
    "webpageUrl": raw.get("webpage_url") or original_url,
    "title": raw.get("title") or "Untitled",
    "description": raw.get("description"),
    "uploader": raw.get("uploader") or raw.get("channel"),
    "thumbnail": raw.get("thumbnail"),
    "duration": duration,
    "extractor": raw.get("extractor_key") or raw.get("extractor"),
    "formats": formats,
  }

"""Turns raw yt-dlp output into the normalized shape the UI consumes.

The UI never sees a yt-dlp field name. Everything it renders is produced here.
"""

import re
from urllib.parse import urlparse

from errors import ExtractorError


MAX_URL_LENGTH = 2048

# yt-dlp's --format argument is a small expression language: "bv+ba/b",
# "best[height<480]" and so on are all valid. Format ids come from a resolve
# result, but they arrive back over the protocol, so they are checked against
# the shape of a real id rather than trusted. This keeps the selector to
# something FetchTube built, not something a caller supplied.
FORMAT_ID_PATTERN = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9_.\-]{0,63}\Z")

# KIKX reads a micro process' stdout with a 10 MB per-line cap
# (kikx/services/micro/main.py). A resolve result carrying several hundred
# formats with full signed URLs can approach that, and exceeding it kills the
# reader for the rest of the session. These caps keep one line well clear of it.
MAX_FORMATS = 120
MAX_DESCRIPTION_CHARS = 600

# Containers a WebView <video> element can be expected to play directly.
DIRECTLY_PLAYABLE_EXTENSIONS = frozenset(
  {"mp4", "m4v", "m4a", "webm", "ogg", "ogv", "mp3", "wav", "aac", "flac", "opus"}
)

AUDIO_ONLY_EXTENSIONS = frozenset(
  {"mp3", "m4a", "aac", "opus", "flac", "wav", "ogg", "oga", "weba"}
)

STREAMING_PROTOCOL_MARKERS = ("m3u8", "dash", "rtmp", "rtsp", "ism")


# ---------------------- Input validation
def require_media_url(value) -> str:
  if not isinstance(value, str):
    raise ExtractorError("invalid_url", "A URL string is required.")

  text = value.strip()

  if not text:
    raise ExtractorError("invalid_url", "The URL is empty.")

  if len(text) > MAX_URL_LENGTH:
    raise ExtractorError("invalid_url", "The URL is too long.")

  parsed = urlparse(text)

  if parsed.scheme not in ("http", "https"):
    raise ExtractorError("invalid_url", "Only http and https URLs are accepted.")

  if not parsed.hostname:
    raise ExtractorError("invalid_url", "The URL has no host.")

  # Credentials would end up in the process argument list and in any error text
  # echoed back to the UI.
  if parsed.username or parsed.password:
    raise ExtractorError("invalid_url", "The URL must not contain credentials.")

  return text


def require_format_id(value) -> str:
  format_id = str(value or "").strip()

  if not FORMAT_ID_PATTERN.match(format_id):
    raise ExtractorError("format_unavailable", "That format is not selectable.")

  return format_id


def optional_format_id(value):
  text = str(value or "").strip()

  return require_format_id(text) if text else None


# ---------------------- Filenames
def safe_filename_stem(title) -> str:
  raw = title if isinstance(title, str) else ""

  kept = [
    character if (character.isalnum() or character in " ._-+()[]&',") else "_"
    for character in raw
  ]

  stem = "".join(kept).strip(" ._")

  while "__" in stem:
    stem = stem.replace("__", "_")

  return stem[:80] or "media"


def safe_extension(value) -> str:
  suffix = str(value or "").lstrip(".").lower()

  if suffix.isalnum() and 1 <= len(suffix) <= 8:
    return suffix

  return "bin"


# ---------------------- Track classification
def _codec(raw: dict, key: str):
  """yt-dlp distinguishes three cases and so must we: a codec name, the literal
  string "none" meaning the stream is genuinely absent, and a missing or null
  field meaning yt-dlp never found out. Treating "unknown" as "absent" is how a
  perfectly good direct link ends up reported as having no usable formats.

  Returns (codec name or None, whether yt-dlp actually knows).
  """
  if key not in raw:
    return None, False

  value = raw[key]

  if value is None:
    return None, False

  text = str(value).strip()

  if not text:
    return None, False

  if text.lower() in ("none", "null"):
    return None, True

  return text, True


def _positive_number(value):
  try:
    number = float(value)
  except (TypeError, ValueError):
    return None

  return number if number > 0 else None


def classify_track(raw: dict):
  """Returns (kind, codecs_known) where kind is muxed, video or audio."""
  video_codec, video_known = _codec(raw, "vcodec")
  audio_codec, audio_known = _codec(raw, "acodec")

  if video_known and audio_known:
    if video_codec and audio_codec:
      return "muxed", True
    if video_codec:
      return "video", True
    if audio_codec:
      return "audio", True

    # Both explicitly absent: there is nothing to download.
    return None, True

  # yt-dlp could not describe this stream. The container is the only evidence
  # left, and the UI is told the codecs are a guess so it can say so.
  if safe_extension(raw.get("ext")) in AUDIO_ONLY_EXTENSIONS:
    return "audio", False

  if video_known and video_codec:
    # Video confirmed, audio a question mark. Calling this "video only" would
    # push the user down the merge path for a file that may already have sound.
    return "muxed", False

  if audio_known and audio_codec:
    return "audio", False

  return "muxed", False


def is_directly_playable(track: dict) -> bool:
  """True when a <video> element can load this URL unaided. Video-only tracks
  are excluded because they would play silently, which reads as a bug."""
  if track["kind"] not in ("muxed", "audio"):
    return False

  if safe_extension(track.get("ext")) not in DIRECTLY_PLAYABLE_EXTENSIONS:
    return False

  protocol = str(track.get("protocol") or "").lower()

  if any(marker in protocol for marker in STREAMING_PROTOCOL_MARKERS):
    return False

  return urlparse(track.get("url") or "").scheme in ("http", "https")


def normalize_track(raw: dict):
  kind, codecs_known = classify_track(raw)

  if kind is None:
    return None

  format_id = str(raw.get("format_id") or "").strip()

  if not format_id:
    return None

  width = raw.get("width")
  height = raw.get("height")
  resolution = raw.get("resolution")

  if not resolution and width and height:
    resolution = f"{width}x{height}"

  track = {
    "id": format_id,
    "kind": kind,
    "codecsKnown": codecs_known,
    "ext": safe_extension(raw.get("ext")),
    "resolution": resolution,
    "width": width,
    "height": height,
    "fps": _positive_number(raw.get("fps")),
    "videoCodec": _codec(raw, "vcodec")[0],
    "audioCodec": _codec(raw, "acodec")[0],
    "sizeBytes": raw.get("filesize") or raw.get("filesize_approx"),
    "bitrateKbps": _positive_number(raw.get("tbr")),
    "audioBitrateKbps": _positive_number(raw.get("abr")),
    "protocol": raw.get("protocol"),
    "note": raw.get("format_note"),
    "url": raw.get("url"),
  }

  track["playable"] = is_directly_playable(track)

  return track


# ---------------------- Media
def _track_rank(track: dict):
  return (
    track.get("height") or 0,
    track.get("bitrateKbps") or track.get("audioBitrateKbps") or 0,
    track.get("sizeBytes") or 0,
  )


def _select_tracks(raw: dict) -> list:
  candidates = raw.get("formats") or raw.get("requested_formats") or []

  tracks = []

  for candidate in candidates:
    if not isinstance(candidate, dict):
      continue

    track = normalize_track(candidate)

    if track is not None:
      tracks.append(track)

  ordered = sorted(tracks, key=_track_rank, reverse=True)

  # Dropping the lowest ranked tail is better than losing the whole response to
  # the stdout line cap.
  return ordered[:MAX_FORMATS]


def _trimmed_description(value):
  if not isinstance(value, str):
    return None

  text = value.strip()

  if not text:
    return None

  if len(text) <= MAX_DESCRIPTION_CHARS:
    return text

  return text[:MAX_DESCRIPTION_CHARS].rstrip() + "…"


def normalize_media(raw: dict, requested_url: str) -> dict:
  return {
    "requestedUrl": requested_url,
    "pageUrl": raw.get("webpage_url") or requested_url,
    "title": (raw.get("title") or "Untitled").strip() or "Untitled",
    "description": _trimmed_description(raw.get("description")),
    "uploader": raw.get("uploader") or raw.get("channel") or raw.get("uploader_id"),
    "thumbnail": raw.get("thumbnail"),
    "durationSeconds": _positive_number(raw.get("duration")),
    "source": raw.get("extractor_key") or raw.get("extractor"),
    "isLive": bool(raw.get("is_live")),
    "formats": _select_tracks(raw),
  }


def first_playlist_entry(payload: dict) -> dict:
  """Some sites return a playlist envelope even with --no-playlist. Resolving
  the first entry is the useful behaviour; the UI says only one item was read."""
  entries = [entry for entry in (payload.get("entries") or []) if isinstance(entry, dict)]

  if not entries:
    raise ExtractorError("media_unavailable", "The link did not contain any media.")

  return entries[0]

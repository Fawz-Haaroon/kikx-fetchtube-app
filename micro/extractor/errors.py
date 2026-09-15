"""Error codes shared with the UI. The UI maps codes to text; the messages here
are the fallback it shows when it does not recognise a code."""


class ExtractorError(Exception):
  def __init__(self, code: str, message: str) -> None:
    super().__init__(message)
    self.code = code
    self.message = message

  def as_dict(self) -> dict:
    return {"code": self.code, "message": self.message}


# Ordered most specific first: "video unavailable" also contains "unavailable",
# and a private video also mentions signing in.
_FAILURE_SIGNATURES = (
  ("private_media", ("private video", "video is private")),
  ("removed_media", ("has been removed", "video has been deleted", "account associated with this video")),
  ("age_restricted", ("confirm your age", "age-restricted", "age restricted")),
  ("sign_in_required", ("sign in to confirm", "login required", "requires authentication",
                        "use --cookies", "confirm you're not a bot")),
  ("geo_blocked", ("not available in your country", "geo restricted", "geo-restricted",
                   "blocked it in your country")),
  ("live_stream", ("is live", "live event will begin", "premieres in")),
  ("unsupported_site", ("unsupported url", "no suitable extractor")),
  ("format_unavailable", ("requested format is not available", "no video formats found")),
  ("media_unavailable", ("http error 404", "404: file not found", "404: not found")),
  ("network_failure", ("urlopen error", "timed out", "temporary failure in name resolution",
                       "connection reset", "unable to download webpage")),
  ("blocked_by_site", ("http error 403", "http error 429", "forbidden", "too many requests")),
  ("media_unavailable", ("video unavailable", "not available", "unavailable")),
)


def classify_yt_dlp_failure(stderr_text: str) -> str:
  haystack = (stderr_text or "").lower()

  for code, needles in _FAILURE_SIGNATURES:
    if any(needle in haystack for needle in needles):
      return code

  return "extractor_failure"


def readable_failure(text: str):
  """yt-dlp prefixes its diagnostics with "ERROR:" and the extractor name. The
  UI renders a code-specific sentence; this is the detail line under it."""
  for line in reversed((text or "").splitlines()):
    stripped = line.strip()

    if not stripped or stripped.startswith("[download]"):
      continue

    for prefix in ("ERROR: ", "WARNING: "):
      if stripped.startswith(prefix):
        stripped = stripped[len(prefix):]

    return stripped

  return None

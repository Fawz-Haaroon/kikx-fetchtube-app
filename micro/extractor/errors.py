class ExtractorError(Exception):
  def __init__(self, code, message):
    super().__init__(message)
    self.code = code
    self.message = message

  def as_dict(self):
    return {"code": self.code, "message": self.message}


def classify_yt_dlp_error(text):
  lower = (text or "").lower()

  if "unsupported url" in lower or "no video formats" in lower:
    return "unsupported_url"
  if "private video" in lower or "this video is private" in lower:
    return "private"
  if "login" in lower or "sign in" in lower or "confirm your age" in lower:
    return "auth_required"
  if "has been removed" in lower or "video has been deleted" in lower:
    return "deleted"
  if "unavailable" in lower or "not available" in lower:
    return "unavailable"
  if "http error 403" in lower or "blocked" in lower or "forbidden" in lower:
    return "blocked"
  if "timed out" in lower or "timeout" in lower or "network" in lower or "urlopen error" in lower:
    return "network"
  if "requested format" in lower or "format is not available" in lower:
    return "missing_format"
  return "extractor_failure"

const MESSAGES = {
  invalid_url: "That does not look like an http(s) URL.",
  unsupported_url: "This site is not supported by the extractor.",
  unavailable: "The media is not available.",
  private: "This media is private.",
  deleted: "This media has been deleted.",
  auth_required: "This media requires a sign-in the extractor cannot provide.",
  network: "The network request failed.",
  extractor_failure: "The extractor could not read this URL.",
  blocked: "The site blocked the request.",
  missing_format: "No usable formats were returned.",
  expired: "The media URL has expired. Resolve the page again.",
  dependency_failure: "yt-dlp is not installed in this KIKX environment.",
  cancelled: "The download was cancelled.",
  filesystem: "The file could not be stored.",
  download_failure: "The download failed.",
  runtime: "The KIKX extractor service is not available."
};

export function messageForError(error) {
  if (!error) {
    return MESSAGES.extractor_failure;
  }
  if (typeof error === "string") {
    return error;
  }
  const code = error.code;
  if (code && MESSAGES[code]) {
    return MESSAGES[code];
  }
  return error.message || MESSAGES.extractor_failure;
}

export function errorFromUnknown(error) {
  if (error && error.code) {
    return error;
  }
  return {
    code: "extractor_failure",
    message: messageForError(error)
  };
}

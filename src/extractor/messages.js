/** Every error code the extractor can send, in the words the user reads.
 *  The extractor also sends a detail sentence; it is shown underneath when it
 *  adds something the code does not already say. */

const MESSAGES = {
  invalid_url: "That is not a valid http or https link.",
  unsupported_site: "yt-dlp has no extractor for this site.",
  media_unavailable: "This media is not available.",
  private_media: "This media is private.",
  removed_media: "This media has been removed.",
  age_restricted: "This media is age restricted and cannot be opened without signing in.",
  sign_in_required: "This media requires a signed-in account.",
  geo_blocked: "This media is blocked in your region.",
  live_stream: "This is a live stream. FetchTube handles finished media only.",
  blocked_by_site: "The site refused the request.",
  network_failure: "The network request failed.",
  format_unavailable: "No downloadable format was offered for this link.",
  merge_failed: "The video and audio streams could not be combined.",
  storage_failure: "The file could not be stored.",
  file_not_found: "That file is no longer stored.",
  job_not_found: "That download is not in the list.",
  job_not_active: "That download has already finished.",
  job_exists: "That download is already running.",
  yt_dlp_missing: "yt-dlp is not installed in this KIKX environment.",
  extractor_failure: "The extractor could not read this link.",
  unknown_operation: "FetchTube asked the extractor for something it does not support.",
  malformed_command: "The extractor received a malformed command.",
  no_response: "The extractor did not respond.",
  service_unavailable: "The extraction service is not running."
};

export function describe(error) {
  if (!error) {
    return MESSAGES.extractor_failure;
  }

  return MESSAGES[error.code] || error.message || MESSAGES.extractor_failure;
}

/** The extractor's own sentence, when it says more than the code alone. */
export function detailOf(error) {
  if (!error?.message) {
    return null;
  }

  return MESSAGES[error.code] && MESSAGES[error.code] !== error.message ? error.message : null;
}

export function codeOf(error) {
  return error?.code || "extractor_failure";
}

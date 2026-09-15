"""FetchTube extraction service.

KIKX starts this as a micro service (kikx/services/micro/main.py): one long
lived process per app, commands arriving on stdin one JSON object per line and
results leaving on stdout the same way. Nothing else may be written to stdout —
diagnostics go to stderr, which KIKX collects separately.
"""

import json
import signal
import sys
import threading
import traceback
import uuid

import storage
import ytdlp
from errors import ExtractorError
from jobs import DownloadJob, DownloadRegistry


# How long a shutdown waits for cancelled downloads to tear themselves down.
SHUTDOWN_GRACE_SECONDS = 5.0
from media import (
  first_playlist_entry,
  normalize_media,
  optional_format_id,
  require_format_id,
  require_media_url,
)


class ExtractorService:
  def __init__(self) -> None:
    # KIKX launches this process without -u when stdout capture is on, so every
    # write must be flushed explicitly or nothing reaches the app.
    self._stdout_lock = threading.Lock()
    self.jobs = DownloadRegistry(self.publish)

  # ---------------------- Output
  def publish(self, payload: dict) -> None:
    line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    with self._stdout_lock:
      sys.stdout.write(line + "\n")
      sys.stdout.flush()

  def reply(self, request_id, payload: dict) -> None:
    self.publish({"id": request_id, **payload})

  def reply_error(self, request_id, code: str, message: str) -> None:
    self.reply(request_id, {"type": "error", "code": code, "message": message})

  # ---------------------- Operations
  def op_probe(self, request_id, _message: dict) -> None:
    self.reply(request_id, {"type": "environment", "environment": ytdlp.probe_environment()})

  def op_resolve(self, request_id, message: dict) -> None:
    url = require_media_url(message.get("url"))
    payload = ytdlp.resolve_metadata(url)

    if payload.get("_type") == "playlist":
      payload = first_playlist_entry(payload)

    media = normalize_media(payload, url)

    if not media["formats"]:
      raise ExtractorError("format_unavailable", "No usable formats were returned.")

    self.reply(request_id, {"type": "media", "media": media})

  def op_download(self, request_id, message: dict) -> None:
    url = require_media_url(message.get("url"))
    video_format_id = require_format_id(message.get("videoFormatId"))
    audio_format_id = optional_format_id(message.get("audioFormatId"))

    job = DownloadJob(
      job_id=str(message.get("jobId") or uuid.uuid4().hex),
      url=url,
      title=str(message.get("title") or "media"),
      format_label=str(message.get("formatLabel") or ""),
      video_format_id=video_format_id,
      audio_format_id=audio_format_id,
    )

    self.jobs.start(job)
    self.reply(request_id, {"type": "accepted", "jobId": job.id})

  def op_cancel(self, request_id, message: dict) -> None:
    self.jobs.cancel(str(message.get("jobId") or ""))
    self.reply(request_id, {"type": "ok"})

  def op_forget(self, request_id, message: dict) -> None:
    self.jobs.forget(str(message.get("jobId") or ""))
    self.reply(request_id, {"type": "ok"})

  def op_jobs(self, request_id, _message: dict) -> None:
    self.reply(request_id, {"type": "jobs", "jobs": self.jobs.snapshots()})

  def op_library(self, request_id, _message: dict) -> None:
    self.reply(request_id, {"type": "library", "entries": storage.library_entries()})

  def op_delete(self, request_id, message: dict) -> None:
    filename = str(message.get("filename") or "")

    if not storage.delete_from_library(filename):
      raise ExtractorError("file_not_found", "That file is no longer stored.")

    self.reply(request_id, {"type": "deleted", "filename": filename})

  # Operations that block on the network run on their own thread so a cancel or
  # a second request is never stuck behind them.
  OPERATIONS = {
    "probe": (op_probe, True),
    "resolve": (op_resolve, True),
    "download": (op_download, False),
    "cancel": (op_cancel, False),
    "forget": (op_forget, False),
    "jobs": (op_jobs, False),
    "library": (op_library, False),
    "delete": (op_delete, False),
  }

  # ---------------------- Dispatch
  def handle(self, message: dict) -> None:
    request_id = message.get("id")
    operation = message.get("op")

    entry = self.OPERATIONS.get(operation)

    if entry is None:
      self.reply_error(request_id, "unknown_operation", f"Unknown operation: {operation}")
      return

    handler, run_detached = entry

    if run_detached:
      threading.Thread(
        target=self._invoke,
        args=(handler, request_id, message),
        name=f"{operation}-{request_id}",
        daemon=True,
      ).start()
      return

    self._invoke(handler, request_id, message)

  def _invoke(self, handler, request_id, message: dict) -> None:
    try:
      handler(self, request_id, message)

    except ExtractorError as error:
      self.reply_error(request_id, error.code, error.message)

    except Exception:  # noqa: BLE001 - one bad request must not end the session
      traceback.print_exc(file=sys.stderr)
      self.reply_error(request_id, "extractor_failure", "The extractor failed unexpectedly.")

  # ---------------------- Lifecycle
  def shut_down(self) -> None:
    """Stop yt-dlp children and give their workers a moment to remove their
    workspaces. Anything still left is cleared by the next startup."""
    self.jobs.cancel_all()
    self.jobs.wait_for_idle(SHUTDOWN_GRACE_SECONDS)

  def serve(self) -> None:
    storage.clear_stale_workspaces()

    signal.signal(signal.SIGTERM, self._on_terminate)

    self.publish({"type": "ready"})

    for raw_line in sys.stdin:
      line = raw_line.strip()

      if not line:
        continue

      try:
        message = json.loads(line)
      except json.JSONDecodeError:
        self.reply_error(None, "malformed_command", "The command was not valid JSON.")
        continue

      if isinstance(message, dict):
        self.handle(message)
      else:
        self.reply_error(None, "malformed_command", "The command must be an object.")

    # stdin closed: KIKX has taken the app down.
    self.shut_down()

  def _on_terminate(self, _signum, _frame) -> None:
    self.shut_down()
    raise SystemExit(0)


if __name__ == "__main__":
  ExtractorService().serve()

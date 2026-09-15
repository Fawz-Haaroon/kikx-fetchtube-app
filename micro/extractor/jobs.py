"""Download job lifecycle.

Every state change produces a complete job snapshot rather than a delta. The UI
replaces a job by id, so a client that reconnects mid-download or misses an
update still converges on the truth without replaying anything.
"""

import threading
import time
from pathlib import Path

import storage
from errors import ExtractorError, classify_yt_dlp_failure, readable_failure
from ytdlp import DownloadProcess, format_selector, progress_from_line


# Two at a time. A phone downloading four large files at once finishes none of
# them sooner and competes with the KIKX runtime for the same CPU and radio.
MAX_CONCURRENT_DOWNLOADS = 2

# KIKX exposes a micro process' stdout as one array that is re-sent in full on
# every poll (kikx/services/micro/main.py has no cursor). Emitting a line per
# yt-dlp progress update would make each poll larger than the last, so progress
# is published at most this often per job.
PROGRESS_INTERVAL_SECONDS = 1.0

ACTIVE_STATES = frozenset({"queued", "downloading", "merging", "storing"})


def _now_milliseconds() -> int:
  return int(time.time() * 1000)


class DownloadJob:
  def __init__(
    self,
    job_id: str,
    url: str,
    title: str,
    format_label: str,
    video_format_id: str,
    audio_format_id,
  ) -> None:
    self.id = job_id
    self.url = url
    self.title = title
    self.format_label = format_label
    self.selector = format_selector(video_format_id, audio_format_id)

    self.state = "queued"
    self.downloaded_bytes = 0
    self.total_bytes = None
    self.speed_bytes_per_second = None
    self.eta_seconds = None
    self.stored_filename = None
    self.stored_relative_path = None
    self.stored_size_bytes = None
    self.error = None

    self.started_at = _now_milliseconds()
    self.ended_at = None

    self.process = None
    self._cancel_requested = False

  @property
  def is_active(self) -> bool:
    return self.state in ACTIVE_STATES

  @property
  def percent(self):
    if not self.total_bytes:
      return None

    return round(min(100.0, self.downloaded_bytes * 100.0 / self.total_bytes), 1)

  def snapshot(self) -> dict:
    return {
      "id": self.id,
      "state": self.state,
      "title": self.title,
      "formatLabel": self.format_label,
      "sourceUrl": self.url,
      "downloadedBytes": self.downloaded_bytes,
      "totalBytes": self.total_bytes,
      "percent": self.percent,
      "speedBytesPerSecond": self.speed_bytes_per_second,
      "etaSeconds": self.eta_seconds,
      "filename": self.stored_filename,
      "relativePath": self.stored_relative_path,
      "sizeBytes": self.stored_size_bytes,
      "error": self.error,
      "startedAt": self.started_at,
      "endedAt": self.ended_at,
    }

  def request_cancel(self) -> None:
    self._cancel_requested = True

    if self.process is not None:
      self.process.cancel()

  @property
  def cancel_requested(self) -> bool:
    return self._cancel_requested


class DownloadRegistry:
  def __init__(self, publish) -> None:
    self._publish = publish
    self._jobs = {}
    self._lock = threading.Lock()
    self._slots = threading.Semaphore(MAX_CONCURRENT_DOWNLOADS)

  # ---------------------- Access
  def snapshots(self) -> list:
    with self._lock:
      return [job.snapshot() for job in self._jobs.values()]

  def has_active_jobs(self) -> bool:
    with self._lock:
      return any(job.is_active for job in self._jobs.values())

  def cancel(self, job_id: str) -> None:
    with self._lock:
      job = self._jobs.get(job_id)

    if job is None:
      raise ExtractorError("job_not_found", "That download is not in the list.")

    if not job.is_active:
      raise ExtractorError("job_not_active", "That download has already finished.")

    job.request_cancel()

  def cancel_all(self) -> None:
    """Used on shutdown. yt-dlp children run in their own process groups so
    that cancelling one also stops its ffmpeg, which means they do not receive
    the signal KIKX sends to this service and have to be stopped here."""
    with self._lock:
      running = [job for job in self._jobs.values() if job.is_active]

    for job in running:
      job.request_cancel()

  def wait_for_idle(self, timeout_seconds: float) -> bool:
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
      if not self.has_active_jobs():
        return True

      time.sleep(0.05)

    return not self.has_active_jobs()

  def forget(self, job_id: str) -> None:
    with self._lock:
      job = self._jobs.get(job_id)

      if job is None or job.is_active:
        return

      del self._jobs[job_id]

  # ---------------------- Start
  def start(self, job: DownloadJob) -> None:
    with self._lock:
      if job.id in self._jobs:
        raise ExtractorError("job_exists", "That download was already started.")

      self._jobs[job.id] = job

    self._emit(job)

    threading.Thread(
      target=self._run_to_completion,
      args=(job,),
      name=f"download-{job.id}",
      daemon=True,
    ).start()

  # ---------------------- Worker
  def _run_to_completion(self, job: DownloadJob) -> None:
    self._slots.acquire()

    try:
      if job.cancel_requested:
        self._finish_cancelled(job)
        return

      self._download(job)

    except ExtractorError as error:
      self._finish_failed(job, error.code, error.message)

    except Exception as error:  # noqa: BLE001 - the worker must never die silently
      self._finish_failed(job, "extractor_failure", str(error) or "The download failed.")

    finally:
      storage.discard_workspace(job.id)
      self._slots.release()

  def _download(self, job: DownloadJob) -> None:
    workspace = storage.job_workspace(job.id)

    job.state = "downloading"
    self._emit(job)

    process = DownloadProcess(
      job.url,
      job.selector,
      str(workspace / "media.%(ext)s"),
    )
    job.process = process

    last_emit = 0.0

    def handle_line(line: str) -> None:
      nonlocal last_emit

      progress = progress_from_line(line)

      if progress is None:
        # yt-dlp announces post-processing on its own lines. Merging is the one
        # phase long enough to be worth showing.
        if "[Merger]" in line and job.state == "downloading":
          job.state = "merging"
          self._emit(job)

        return

      if progress["downloadedBytes"] is not None:
        job.downloaded_bytes = progress["downloadedBytes"]

      if progress["totalBytes"] is not None:
        job.total_bytes = progress["totalBytes"]

      job.speed_bytes_per_second = progress["speedBytesPerSecond"]
      job.eta_seconds = progress["etaSeconds"]

      now = time.monotonic()

      if now - last_emit >= PROGRESS_INTERVAL_SECONDS:
        last_emit = now
        self._emit(job)

    returncode = process.run(handle_line)

    if job.cancel_requested:
      self._finish_cancelled(job)
      return

    if returncode != 0:
      failure_text = process.recent_output()

      raise ExtractorError(
        classify_yt_dlp_failure(failure_text),
        readable_failure(failure_text) or "The download did not complete.",
      )

    self._store(job, workspace)

  def _store(self, job: DownloadJob, workspace: Path) -> None:
    job.state = "storing"
    job.speed_bytes_per_second = None
    job.eta_seconds = None
    self._emit(job)

    produced = [path for path in workspace.iterdir() if path.is_file()]

    if not produced:
      raise ExtractorError("storage_failure", "yt-dlp produced no file.")

    if len(produced) > 1:
      # Separate video and audio streams left side by side means the merge step
      # never ran, which in practice means ffmpeg is missing.
      raise ExtractorError(
        "merge_failed",
        "The video and audio streams could not be merged. Install ffmpeg.",
      )

    stored = storage.store_download(produced[0], job.title)

    job.stored_filename = stored.name
    job.stored_relative_path = storage.relative_to_data(stored)
    job.stored_size_bytes = stored.stat().st_size
    job.downloaded_bytes = job.stored_size_bytes

    if not job.total_bytes:
      job.total_bytes = job.stored_size_bytes

    job.state = "completed"
    job.ended_at = _now_milliseconds()
    self._emit(job)

  # ---------------------- Terminal states
  def _finish_cancelled(self, job: DownloadJob) -> None:
    job.state = "cancelled"
    job.ended_at = _now_milliseconds()
    job.speed_bytes_per_second = None
    job.eta_seconds = None
    self._emit(job)

  def _finish_failed(self, job: DownloadJob, code: str, message: str) -> None:
    job.state = "failed"
    job.ended_at = _now_milliseconds()
    job.speed_bytes_per_second = None
    job.eta_seconds = None
    job.error = {"code": code, "message": message}
    self._emit(job)

  def _emit(self, job: DownloadJob) -> None:
    self._publish({"type": "job", "job": job.snapshot()})

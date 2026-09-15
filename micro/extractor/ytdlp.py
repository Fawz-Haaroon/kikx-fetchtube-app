"""Every yt-dlp invocation in FetchTube goes through this module.

Commands are always built as argument lists. No value that came from the UI is
ever placed in a shell string.
"""

import json
import os
import shutil
import signal
import subprocess
import sys
import threading

from errors import ExtractorError, classify_yt_dlp_failure, readable_failure


RESOLVE_TIMEOUT_SECONDS = 180
PROBE_TIMEOUT_SECONDS = 20

# Emitted once per progress update and parsed back in progress_from_line.
# The prefix keeps progress lines apart from anything else yt-dlp writes.
PROGRESS_PREFIX = "@fetchtube@"
PROGRESS_TEMPLATE = (
  "download:" + PROGRESS_PREFIX + "%(progress.status)s\t"
  "%(progress.downloaded_bytes)s\t"
  "%(progress.total_bytes)s\t"
  "%(progress.total_bytes_estimate)s\t"
  "%(progress.speed)s\t"
  "%(progress.eta)s"
)

BASE_ARGS = (
  "--no-warnings",
  "--no-playlist",
  "--no-color",
  "--ignore-config",
)


def _yt_dlp_command() -> list:
  """Prefer the packaged binary (Termux `pkg install yt-dlp`), fall back to the
  module inside the interpreter running this service (`pip install yt-dlp`)."""
  binary = shutil.which("yt-dlp")

  if binary:
    return [binary]

  return [sys.executable, "-m", "yt_dlp"]


def _missing_dependency_error() -> ExtractorError:
  return ExtractorError(
    "yt_dlp_missing",
    "yt-dlp was not found in this KIKX environment.",
  )


def _looks_like_missing_module(text: str) -> bool:
  lowered = (text or "").lower()

  return "no module named" in lowered and "yt_dlp" in lowered


def probe_environment() -> dict:
  """What the host can actually do. The UI uses this to avoid offering
  operations that would fail."""
  version = None

  try:
    completed = subprocess.run(
      [*_yt_dlp_command(), "--version"],
      capture_output=True,
      text=True,
      timeout=PROBE_TIMEOUT_SECONDS,
      check=False,
    )

    if completed.returncode == 0:
      version = completed.stdout.strip() or None

  except (OSError, subprocess.SubprocessError):
    version = None

  return {
    "ytDlpVersion": version,
    "hasFfmpeg": shutil.which("ffmpeg") is not None,
    "pythonVersion": ".".join(str(part) for part in sys.version_info[:3]),
  }


def resolve_metadata(url: str) -> dict:
  command = [
    *_yt_dlp_command(),
    *BASE_ARGS,
    "--dump-single-json",
    "--skip-download",
    "--no-progress",
    "--",
    url,
  ]

  try:
    completed = subprocess.run(
      command,
      capture_output=True,
      text=True,
      timeout=RESOLVE_TIMEOUT_SECONDS,
      check=False,
    )
  except FileNotFoundError as error:
    raise _missing_dependency_error() from error
  except subprocess.TimeoutExpired as error:
    raise ExtractorError("network_failure", "Resolving the link timed out.") from error

  if completed.returncode != 0:
    failure_text = (completed.stderr or completed.stdout or "").strip()

    if _looks_like_missing_module(failure_text):
      raise _missing_dependency_error()

    raise ExtractorError(
      classify_yt_dlp_failure(failure_text),
      readable_failure(failure_text) or "yt-dlp failed.",
    )

  try:
    return json.loads(completed.stdout)
  except json.JSONDecodeError as error:
    raise ExtractorError(
      "extractor_failure",
      "yt-dlp returned something that was not JSON.",
    ) from error


def _numeric_field(token: str):
  # yt-dlp renders absent template fields as "NA".
  if token in ("", "NA", "None", "none"):
    return None

  try:
    return int(float(token))
  except ValueError:
    return None


def progress_from_line(line: str):
  """Parse one --progress-template line. Returns None for every other line."""
  marker = line.find(PROGRESS_PREFIX)

  if marker < 0:
    return None

  fields = line[marker + len(PROGRESS_PREFIX):].strip().split("\t")

  if len(fields) != 6:
    return None

  status, downloaded, total, estimate, speed, eta = fields

  return {
    "status": status,
    "downloadedBytes": _numeric_field(downloaded),
    "totalBytes": _numeric_field(total) or _numeric_field(estimate),
    "speedBytesPerSecond": _numeric_field(speed),
    "etaSeconds": _numeric_field(eta),
  }


def format_selector(video_id: str, audio_id) -> str:
  return f"{video_id}+{audio_id}" if audio_id else video_id


class DownloadProcess:
  """A single yt-dlp download. Output is streamed line by line so progress is
  reported from yt-dlp's own numbers rather than estimated here."""

  def __init__(self, url: str, selector: str, output_template: str) -> None:
    self.command = [
      *_yt_dlp_command(),
      *BASE_ARGS,
      "--newline",
      "--progress",
      "--progress-template",
      PROGRESS_TEMPLATE,
      "--retries",
      "3",
      "--fragment-retries",
      "3",
      "--format",
      selector,
      "--output",
      output_template,
      "--",
      url,
    ]

    self._process = None
    self._cancelled = False
    self._lock = threading.Lock()
    self._tail = []

  @property
  def was_cancelled(self) -> bool:
    return self._cancelled

  def recent_output(self) -> str:
    return "\n".join(self._tail)

  def run(self, on_line) -> int:
    """Start yt-dlp and feed each output line to on_line. Returns the exit code."""
    try:
      process = subprocess.Popen(
        self.command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        # Own process group so cancel also stops ffmpeg started by yt-dlp.
        start_new_session=True,
      )
    except FileNotFoundError as error:
      raise _missing_dependency_error() from error

    with self._lock:
      if self._cancelled:
        # cancel() arrived between construction and spawn.
        self._terminate(process)

      self._process = process

    for raw_line in process.stdout:
      line = raw_line.rstrip("\n")

      # Keep a short tail so a failure can be classified without holding the
      # entire output of a long download in memory.
      self._tail.append(line)
      if len(self._tail) > 20:
        self._tail.pop(0)

      on_line(line)

    returncode = process.wait()

    with self._lock:
      self._process = None

    if _looks_like_missing_module(self.recent_output()):
      raise _missing_dependency_error()

    return returncode

  def cancel(self) -> None:
    with self._lock:
      self._cancelled = True
      process = self._process

    if process is not None:
      self._terminate(process)

  @staticmethod
  def _terminate(process) -> None:
    try:
      os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError):
      try:
        process.terminate()
      except OSError:
        pass

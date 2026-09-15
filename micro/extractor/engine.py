import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from errors import ExtractorError, classify_yt_dlp_error
from media import normalize_media, require_http_url, safe_filename


RESOLVE_TIMEOUT_SECONDS = 180


def data_dir():
  return Path(os.environ.get("KIKX_APP_DATA_PATH") or os.path.join(os.getcwd(), "data"))


def cache_dir():
  return Path(os.environ.get("KIKX_APP_CACHE_PATH") or os.path.join(os.getcwd(), "cache"))


def downloads_dir():
  path = data_dir() / "downloads"
  path.mkdir(parents=True, exist_ok=True)
  return path


def temp_dir():
  path = cache_dir() / "tmp"
  path.mkdir(parents=True, exist_ok=True)
  return path


def find_yt_dlp():
  binary = shutil.which("yt-dlp")
  if binary:
    return [binary]
  return [sys.executable, "-m", "yt_dlp"]


def _run_yt_dlp(args, timeout=None):
  cmd = [*find_yt_dlp(), *args]
  try:
    completed = subprocess.run(
      cmd,
      check=False,
      capture_output=True,
      text=True,
      timeout=timeout,
    )
  except FileNotFoundError as exc:
    raise ExtractorError(
      "dependency_failure",
      "yt-dlp is not installed on this KIKX host.",
    ) from exc
  except subprocess.TimeoutExpired as exc:
    raise ExtractorError("network", "The extractor timed out.") from exc

  if completed.returncode != 0:
    err = (completed.stderr or completed.stdout or "").strip()
    if "No module named yt_dlp" in err or "yt-dlp: not found" in err:
      raise ExtractorError(
        "dependency_failure",
        "yt-dlp is not installed on this KIKX host.",
      )
    raise ExtractorError(classify_yt_dlp_error(err), err or "yt-dlp failed.")
  return completed


def resolve_media(url):
  url = require_http_url(url)
  completed = _run_yt_dlp(
    [
      "--dump-single-json",
      "--no-warnings",
      "--no-playlist",
      "--skip-download",
      url,
    ],
    timeout=RESOLVE_TIMEOUT_SECONDS,
  )
  try:
    payload = json.loads(completed.stdout)
  except json.JSONDecodeError as exc:
    raise ExtractorError(
      "extractor_failure",
      "yt-dlp returned data that was not JSON.",
    ) from exc

  if payload.get("_type") == "playlist":
    entries = payload.get("entries") or []
    if not entries:
      raise ExtractorError("unavailable", "The playlist did not contain any media.")
    payload = entries[0]

  media = normalize_media(payload, url)
  if not media["formats"]:
    raise ExtractorError("missing_format", "No usable media formats were returned.")
  return media


class DownloadJob:
  def __init__(self, job_id, url, format_id, title):
    self.id = job_id
    self.url = require_http_url(url)
    self.format_id = str(format_id)
    self.title = title or "media"
    self.cancel_event = threading.Event()
    self.process = None
    self.temp_path = None
    self.final_path = None

  def cancel(self):
    self.cancel_event.set()
    process = self.process
    if process is not None and process.poll() is None:
      process.terminate()

  def _cleanup_temp(self):
    if self.temp_path is None:
      return
    parent = self.temp_path.parent
    stem = self.temp_path.name
    if parent.is_dir():
      for item in parent.iterdir():
        if item.name == stem or item.name.startswith(stem + "."):
          try:
            item.unlink()
          except OSError:
            pass

  def run(self, on_progress):
    downloads = downloads_dir()
    work = temp_dir()
    ext = "media"
    out_template = work / f"{self.id}.%(ext)s"
    self.temp_path = work / self.id

    cmd = [
      *find_yt_dlp(),
      "--no-warnings",
      "--no-playlist",
      "--newline",
      "-f",
      self.format_id,
      "-o",
      str(out_template),
      "--",
      self.url,
    ]

    try:
      self.process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
      )
    except FileNotFoundError as exc:
      raise ExtractorError(
        "dependency_failure",
        "yt-dlp is not installed on this KIKX host.",
      ) from exc

    last_ext = None
    try:
      for line in self.process.stdout:
        if self.cancel_event.is_set():
          self.process.terminate()
          break
        parsed = parse_progress_line(line)
        if parsed is not None:
          on_progress(parsed)
        marker = "[download] Destination:"
        if marker in line:
          dest = line.split(marker, 1)[1].strip()
          last_ext = Path(dest).suffix.lstrip(".")

      returncode = self.process.wait()
    finally:
      self.process = None

    if self.cancel_event.is_set():
      self._cleanup_temp()
      raise ExtractorError("cancelled", "The download was cancelled.")

    if returncode != 0:
      self._cleanup_temp()
      raise ExtractorError("download_failure", "The download did not complete.")

    produced = None
    for item in work.iterdir():
      if item.name.startswith(self.id) and item.is_file() and not item.name.endswith(".part"):
        produced = item
        break

    if produced is None:
      self._cleanup_temp()
      raise ExtractorError("filesystem", "The downloaded file was not found.")

    ext = last_ext or produced.suffix.lstrip(".") or "bin"
    filename = safe_filename(self.title, ext)
    destination = unique_path(downloads / filename)
    try:
      produced.replace(destination)
    except OSError as exc:
      self._cleanup_temp()
      raise ExtractorError("filesystem", f"Could not store the file: {exc}") from exc

    self.final_path = destination
    return {
      "path": str(destination),
      "filename": destination.name,
      "directory": str(downloads),
    }


def unique_path(path):
  if not path.exists():
    return path
  stem = path.stem
  suffix = path.suffix
  parent = path.parent
  index = 1
  while True:
    candidate = parent / f"{stem}-{index}{suffix}"
    if not candidate.exists():
      return candidate
    index += 1


def parse_progress_line(line):
  text = line.strip()
  if not text.startswith("[download]"):
    return None
  if "%" not in text:
    return None

  percent = None
  downloaded = None
  total = None
  speed = None
  eta = None

  parts = text.split()
  for i, part in enumerate(parts):
    if part.endswith("%"):
      try:
        percent = float(part[:-1])
      except ValueError:
        pass
    if part == "of" and i + 1 < len(parts):
      total = _size_to_bytes(parts[i + 1])
    if part == "at" and i + 1 < len(parts):
      speed = parts[i + 1]
    if part == "ETA" and i + 1 < len(parts):
      eta = parts[i + 1]

  body = text.replace("[download]", "").strip()
  first = body.split("of", 1)[0].strip()
  downloaded = _size_to_bytes(first.replace(f"{percent}%" if percent is not None else "", "").strip())

  return {
    "percent": percent,
    "downloaded": downloaded,
    "total": total,
    "speed": None if speed in (None, "Unknown") else speed,
    "eta": None if eta in (None, "Unknown") else eta,
  }


def _size_to_bytes(token):
  if not token:
    return None
  units = {"B": 1, "KiB": 1024, "MiB": 1024**2, "GiB": 1024**3, "TiB": 1024**4,
           "KB": 1000, "MB": 1000**2, "GB": 1000**3}
  for unit, factor in units.items():
    if token.endswith(unit):
      try:
        return int(float(token[: -len(unit)]) * factor)
      except ValueError:
        return None
  return None

"""Where FetchTube keeps files inside KIKX.

KIKX gives a micro process KIKX_APP_DATA_PATH and KIKX_APP_CACHE_PATH
(kikx/services/micro/main.py) and serves the data path back to the app over
/app-data/<app-id>/<relative path>. Finished media therefore goes in the data
path, and only the data path: nothing here writes outside it.
"""

import os
import shutil
from pathlib import Path

from media import safe_extension, safe_filename_stem


DOWNLOADS_DIRECTORY_NAME = "downloads"


def _environment_path(variable: str, fallback: str) -> Path:
  value = os.environ.get(variable)

  return Path(value) if value else Path.cwd() / fallback


def app_data_path() -> Path:
  return _environment_path("KIKX_APP_DATA_PATH", "data")


def app_cache_path() -> Path:
  return _environment_path("KIKX_APP_CACHE_PATH", "cache")


def downloads_path() -> Path:
  path = app_data_path() / DOWNLOADS_DIRECTORY_NAME
  path.mkdir(parents=True, exist_ok=True)

  return path


def job_workspace(job_id: str) -> Path:
  """A private directory per job. yt-dlp writes fragments, .part files and
  pre-merge streams here, so discarding the directory is a complete cleanup."""
  path = app_cache_path() / "jobs" / job_id
  path.mkdir(parents=True, exist_ok=True)

  return path


def discard_workspace(job_id: str) -> None:
  shutil.rmtree(app_cache_path() / "jobs" / job_id, ignore_errors=True)


def clear_stale_workspaces() -> None:
  """Downloads do not survive a runtime restart, so any workspace present at
  startup belongs to a job that can no longer be completed."""
  shutil.rmtree(app_cache_path() / "jobs", ignore_errors=True)


def unused_path(directory: Path, stem: str, extension: str) -> Path:
  candidate = directory / f"{stem}.{extension}"

  if not candidate.exists():
    return candidate

  index = 2

  while True:
    candidate = directory / f"{stem} ({index}).{extension}"

    if not candidate.exists():
      return candidate

    index += 1


def store_download(produced: Path, title: str) -> Path:
  """Move a finished file out of its workspace into the downloads directory."""
  destination = unused_path(
    downloads_path(),
    safe_filename_stem(title),
    safe_extension(produced.suffix),
  )

  # Workspace and downloads are both under the KIKX app storage root, but they
  # are different directories and a rename across filesystems would fail.
  try:
    produced.replace(destination)
  except OSError:
    shutil.move(str(produced), str(destination))

  return destination


def relative_to_data(path: Path) -> str:
  return path.relative_to(app_data_path()).as_posix()


def library_entries() -> list:
  directory = downloads_path()

  entries = []

  for path in sorted(directory.iterdir()):
    if not path.is_file() or path.name.startswith("."):
      continue

    stats = path.stat()

    entries.append({
      "filename": path.name,
      "relativePath": relative_to_data(path),
      "sizeBytes": stats.st_size,
      "storedAt": int(stats.st_mtime * 1000),
    })

  return sorted(entries, key=lambda entry: entry["storedAt"], reverse=True)


def delete_from_library(filename: str) -> bool:
  """filename is a bare name chosen by the UI from library_entries. Anything
  carrying a path separator is rejected rather than resolved."""
  if not filename or Path(filename).name != filename:
    return False

  target = downloads_path() / filename

  if not target.is_file():
    return False

  target.unlink()

  return True

# JSON-lines protocol on stdin/stdout. Never write logs to stdout.

import json
import sys
import threading
import traceback
import uuid

from errors import ExtractorError
from engine import DownloadJob, resolve_media


def emit(payload):
  sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
  sys.stdout.flush()


class ExtractorProcess:
  def __init__(self):
    self.lock = threading.Lock()
    self.downloads = {}

  def handle(self, message):
    request_id = message.get("id") or str(uuid.uuid4())
    op = message.get("op")

    try:
      if op == "resolve":
        media = resolve_media(message.get("url"))
        emit({"id": request_id, "type": "result", "media": media})
        return

      if op == "download":
        job_id = message.get("jobId") or str(uuid.uuid4())
        job = DownloadJob(
          job_id,
          message.get("url"),
          message.get("formatId"),
          message.get("title"),
        )
        with self.lock:
          self.downloads[job_id] = job
        emit({"id": request_id, "type": "started", "jobId": job_id})

        def on_progress(progress):
          emit({"id": request_id, "type": "progress", "jobId": job_id, **progress})

        result = job.run(on_progress)
        emit({"id": request_id, "type": "complete", "jobId": job_id, **result})
        return

      if op == "cancel":
        job_id = message.get("jobId")
        with self.lock:
          job = self.downloads.get(job_id)
        if job is None:
          raise ExtractorError("download_failure", "That download is not running.")
        job.cancel()
        emit({"id": request_id, "type": "cancelled", "jobId": job_id})
        return

      raise ExtractorError("extractor_failure", f"Unknown operation: {op}")

    except ExtractorError as exc:
      emit({"id": request_id, "type": "error", **exc.as_dict(), "jobId": message.get("jobId")})
    except Exception:
      traceback.print_exc(file=sys.stderr)
      emit({
        "id": request_id,
        "type": "error",
        "code": "extractor_failure",
        "message": "The extractor failed unexpectedly.",
        "jobId": message.get("jobId"),
      })
    finally:
      job_id = message.get("jobId")
      if op == "download" and job_id:
        with self.lock:
          self.downloads.pop(job_id, None)

  def serve(self):
    emit({"type": "ready"})
    for raw in sys.stdin:
      line = raw.strip()
      if not line:
        continue
      try:
        message = json.loads(line)
      except json.JSONDecodeError:
        emit({
          "type": "error",
          "code": "extractor_failure",
          "message": "Malformed extractor command.",
        })
        continue

      op = message.get("op")
      if op == "download":
        threading.Thread(target=self.handle, args=(message,), daemon=True).start()
      else:
        self.handle(message)


if __name__ == "__main__":
  ExtractorProcess().serve()

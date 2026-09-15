"""Local HTTP wrapper around the same extractor used by the KIKX micro service."""

import json
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1] / "micro" / "extractor"
sys.path.insert(0, str(ROOT))

from errors import ExtractorError
from engine import DownloadJob, resolve_media


HOST = "127.0.0.1"
PORT = 8091
JOBS = {}
LOCK = threading.Lock()


def read_json(handler):
  length = int(handler.headers.get("Content-Length") or 0)
  raw = handler.rfile.read(length) if length else b"{}"
  return json.loads(raw.decode("utf-8"))


def send_json(handler, status, payload):
  body = json.dumps(payload).encode("utf-8")
  handler.send_response(status)
  handler.send_header("Content-Type", "application/json")
  handler.send_header("Access-Control-Allow-Origin", "*")
  handler.send_header("Access-Control-Allow-Headers", "content-type")
  handler.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
  handler.send_header("Content-Length", str(len(body)))
  handler.end_headers()
  handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
  def log_message(self, format, *args):
    sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

  def do_OPTIONS(self):
    send_json(self, 204, {})

  def do_GET(self):
    parsed = urlparse(self.path)
    if parsed.path == "/health":
      send_json(self, 200, {"ok": True})
      return
    send_json(self, 404, {"code": "extractor_failure", "message": "Unknown route."})

  def do_POST(self):
    parsed = urlparse(self.path)
    try:
      body = read_json(self)
    except json.JSONDecodeError:
      send_json(self, 400, {"code": "invalid_url", "message": "Malformed JSON."})
      return

    try:
      if parsed.path == "/resolve":
        media = resolve_media(body.get("url"))
        send_json(self, 200, {"media": media})
        return

      if parsed.path == "/download":
        job_id = body.get("jobId") or str(uuid.uuid4())
        job = DownloadJob(job_id, body.get("url"), body.get("formatId"), body.get("title"))
        with LOCK:
          JOBS[job_id] = {"job": job, "progress": None, "result": None, "error": None}

        def run():
          def on_progress(progress):
            with LOCK:
              JOBS[job_id]["progress"] = progress

          try:
            result = job.run(on_progress)
            with LOCK:
              JOBS[job_id]["result"] = result
          except ExtractorError as exc:
            with LOCK:
              JOBS[job_id]["error"] = exc.as_dict()
          except Exception as exc:
            with LOCK:
              JOBS[job_id]["error"] = {
                "code": "download_failure",
                "message": str(exc),
              }

        threading.Thread(target=run, daemon=True).start()
        send_json(self, 200, {"jobId": job_id})
        return

      if parsed.path == "/cancel":
        job_id = body.get("jobId")
        with LOCK:
          entry = JOBS.get(job_id)
        if entry is None:
          raise ExtractorError("download_failure", "That download is not running.")
        entry["job"].cancel()
        send_json(self, 200, {"ok": True})
        return

      if parsed.path == "/status":
        job_id = body.get("jobId")
        with LOCK:
          entry = JOBS.get(job_id)
        if entry is None:
          send_json(self, 404, {"code": "download_failure", "message": "Unknown download."})
          return
        send_json(self, 200, {
          "progress": entry["progress"],
          "result": entry["result"],
          "error": entry["error"],
        })
        return

      send_json(self, 404, {"code": "extractor_failure", "message": "Unknown route."})
    except ExtractorError as exc:
      send_json(self, 400, exc.as_dict())


def main():
  server = ThreadingHTTPServer((HOST, PORT), Handler)
  sys.stderr.write(f"dev extractor on http://{HOST}:{PORT}\n")
  server.serve_forever()


if __name__ == "__main__":
  main()

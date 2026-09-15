"""Runs the extractor outside KIKX for `pnpm dev`.

It exposes the same three operations KIKX's micro service does — start the
process, write a line to its stdin, read the stdout buffer — so the browser code
above the transport is the same code that runs inside KIKX. Only the transport
differs. This is a development tool and binds to the loopback interface only.
"""

import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HOST = "127.0.0.1"
PORT = 8091

ROOT = Path(__file__).resolve().parents[1]
EXTRACTOR = ROOT / "micro" / "extractor" / "main.py"

# Tests point this at a throwaway directory so one run cannot inherit files
# stored by the last one.
WORKSPACE = Path(os.environ.get("FETCHTUBE_DEV_WORKSPACE") or (ROOT / ".dev"))


class Extractor:
  def __init__(self) -> None:
    self.process = None
    self.output = []
    self.lock = threading.Lock()

  def start(self) -> int:
    with self.lock:
      if self.process is not None and self.process.poll() is None:
        return len(self.output)

      data_path = WORKSPACE / "data"
      cache_path = WORKSPACE / "cache"
      data_path.mkdir(parents=True, exist_ok=True)
      cache_path.mkdir(parents=True, exist_ok=True)

      environment = os.environ.copy()
      environment["KIKX_APP_DATA_PATH"] = str(data_path)
      environment["KIKX_APP_CACHE_PATH"] = str(cache_path)

      self.output = []
      self.process = subprocess.Popen(
        [sys.executable, str(EXTRACTOR)],
        cwd=str(data_path),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=None,
        text=True,
        bufsize=1,
        env=environment,
      )

      threading.Thread(target=self._collect, daemon=True).start()

      return 0

  def _collect(self) -> None:
    for line in self.process.stdout:
      stripped = line.rstrip("\n")

      if stripped:
        self.output.append(stripped)

  def send(self, payload: dict) -> None:
    self.start()
    self.process.stdin.write(json.dumps(payload) + "\n")
    self.process.stdin.flush()

  def since(self, index: int) -> list:
    return self.output[max(0, index):]


extractor = Extractor()


class Handler(BaseHTTPRequestHandler):
  protocol_version = "HTTP/1.1"

  def log_message(self, *_args) -> None:
    pass

  def _respond(self, status: int, payload: dict) -> None:
    body = json.dumps(payload).encode("utf-8")

    self.send_response(status)
    self.send_header("Content-Type", "application/json")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)

  def _read_json(self) -> dict:
    length = int(self.headers.get("Content-Length") or 0)

    if not length:
      return {}

    return json.loads(self.rfile.read(length).decode("utf-8"))

  def do_POST(self) -> None:
    route = urlparse(self.path).path

    try:
      if route == "/start":
        self._respond(200, {"lines": extractor.start()})
      elif route == "/send":
        extractor.send(self._read_json())
        self._respond(200, {"ok": True})
      else:
        self._respond(404, {"error": "not found"})

    except Exception as error:  # noqa: BLE001 - development helper
      self._respond(500, {"error": str(error)})

  def do_GET(self) -> None:
    parsed = urlparse(self.path)

    if parsed.path != "/output":
      self._respond(404, {"error": "not found"})
      return

    index = int((parse_qs(parsed.query).get("from") or ["0"])[0])

    self._respond(200, {"output": extractor.since(index)})


if __name__ == "__main__":
  if not EXTRACTOR.is_file():
    raise SystemExit(f"Extractor not found at {EXTRACTOR}")

  print(f"FetchTube development extractor on http://{HOST}:{PORT}")
  print(f"Storage: {WORKSPACE}")

  ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()

"""Serves one file at a fixed rate so the cancellation test can reliably act
while a download is still in flight. Loopback is otherwise fast enough that a
transfer finishes before any progress is reported."""

import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = int(sys.argv[1])
FILE = Path(sys.argv[2])
BYTES_PER_SECOND = int(sys.argv[3]) if len(sys.argv) > 3 else 512 * 1024

CHUNK = 16 * 1024


class Handler(BaseHTTPRequestHandler):
  protocol_version = "HTTP/1.1"

  def log_message(self, *_args):
    pass

  def do_HEAD(self):
    self._headers()

  def _headers(self):
    self.send_response(200)
    self.send_header("Content-Type", "video/mp4")
    self.send_header("Content-Length", str(FILE.stat().st_size))
    self.send_header("Accept-Ranges", "none")
    self.end_headers()

  def do_GET(self):
    self._headers()

    delay = CHUNK / BYTES_PER_SECOND

    with FILE.open("rb") as handle:
      while True:
        chunk = handle.read(CHUNK)

        if not chunk:
          break

        try:
          self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError):
          return

        time.sleep(delay)


ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()

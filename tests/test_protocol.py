"""Exercises the extractor over the wire the way KIKX does: one process, JSON
objects in on stdin, JSON objects out on stdout."""

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

EXTRACTOR = Path(__file__).resolve().parents[1] / "micro" / "extractor" / "main.py"


class ExtractorSession:
  def __init__(self, workspace: Path) -> None:
    environment = os.environ.copy()
    environment["KIKX_APP_DATA_PATH"] = str(workspace / "data")
    environment["KIKX_APP_CACHE_PATH"] = str(workspace / "cache")

    self.process = subprocess.Popen(
      [sys.executable, str(EXTRACTOR)],
      cwd=str(EXTRACTOR.parent),
      stdin=subprocess.PIPE,
      stdout=subprocess.PIPE,
      stderr=subprocess.PIPE,
      text=True,
      bufsize=1,
      env=environment,
    )

    self.messages = []
    threading.Thread(target=self._read, daemon=True).start()

  def _read(self) -> None:
    for line in self.process.stdout:
      stripped = line.strip()

      if stripped:
        self.messages.append(json.loads(stripped))

  def send(self, payload: dict) -> None:
    self.process.stdin.write(json.dumps(payload) + "\n")
    self.process.stdin.flush()

  def send_raw(self, text: str) -> None:
    self.process.stdin.write(text + "\n")
    self.process.stdin.flush()

  def wait_for(self, predicate, timeout: float = 20.0):
    deadline = time.time() + timeout

    while time.time() < deadline:
      for message in list(self.messages):
        if predicate(message):
          return message

      time.sleep(0.02)

    return None

  def close(self) -> None:
    try:
      self.process.stdin.close()
      self.process.wait(timeout=10)
    except Exception:
      self.process.kill()
    finally:
      for stream in (self.process.stdout, self.process.stderr):
        try:
          stream.close()
        except Exception:
          pass


class ProtocolTests(unittest.TestCase):
  def setUp(self) -> None:
    self.workspace = Path(tempfile.mkdtemp(prefix="fetchtube-test-"))
    self.session = ExtractorSession(self.workspace)

    self.assertIsNotNone(
      self.session.wait_for(lambda message: message.get("type") == "ready", 15),
      "the extractor did not announce itself",
    )

  def tearDown(self) -> None:
    self.session.close()

  def test_announces_the_host_environment(self):
    self.session.send({"id": "probe", "op": "probe"})
    reply = self.session.wait_for(lambda message: message.get("id") == "probe")

    self.assertEqual(reply["type"], "environment")
    self.assertIn("hasFfmpeg", reply["environment"])
    self.assertIn("ytDlpVersion", reply["environment"])

  def test_rejects_a_url_that_is_not_http(self):
    self.session.send({"id": "bad", "op": "resolve", "url": "file:///etc/passwd"})
    reply = self.session.wait_for(lambda message: message.get("id") == "bad")

    self.assertEqual(reply["type"], "error")
    self.assertEqual(reply["code"], "invalid_url")

  def test_rejects_an_unknown_operation(self):
    self.session.send({"id": "weird", "op": "rm -rf"})
    reply = self.session.wait_for(lambda message: message.get("id") == "weird")

    self.assertEqual(reply["code"], "unknown_operation")

  def test_survives_a_malformed_line(self):
    self.session.send_raw("{ not json")

    self.assertIsNotNone(
      self.session.wait_for(lambda message: message.get("code") == "malformed_command")
    )

    # The session must still be usable afterwards.
    self.session.send({"id": "after", "op": "jobs"})
    self.assertIsNotNone(self.session.wait_for(lambda message: message.get("id") == "after"))

  def test_reports_an_empty_job_list_and_library(self):
    self.session.send({"id": "jobs", "op": "jobs"})
    jobs = self.session.wait_for(lambda message: message.get("id") == "jobs")

    self.assertEqual(jobs["jobs"], [])

    self.session.send({"id": "lib", "op": "library"})
    library = self.session.wait_for(lambda message: message.get("id") == "lib")

    self.assertEqual(library["entries"], [])

  def test_cancelling_an_unknown_job_is_an_error_not_a_crash(self):
    self.session.send({"id": "cancel", "op": "cancel", "jobId": "does-not-exist"})
    reply = self.session.wait_for(lambda message: message.get("id") == "cancel")

    self.assertEqual(reply["code"], "job_not_found")

  def test_refuses_a_download_without_a_format(self):
    self.session.send(
      {"id": "nofmt", "op": "download", "url": "https://example.com/a", "videoFormatId": ""}
    )
    reply = self.session.wait_for(lambda message: message.get("id") == "nofmt")

    self.assertEqual(reply["code"], "format_unavailable")

  def test_refuses_a_format_selector_expression(self):
    self.session.send({
      "id": "selector",
      "op": "download",
      "url": "https://example.com/a",
      "videoFormatId": "bv+ba/best",
    })
    reply = self.session.wait_for(lambda message: message.get("id") == "selector")

    self.assertEqual(reply["code"], "format_unavailable")

  def test_handles_several_commands_without_interleaving_output(self):
    # resolve runs off the reader thread, so a later command must not queue
    # behind it and every line must still be one complete JSON object.
    for index in range(6):
      self.session.send({"id": f"burst-{index}", "op": "jobs"})

    for index in range(6):
      self.assertIsNotNone(
        self.session.wait_for(lambda message, i=index: message.get("id") == f"burst-{i}"),
        f"reply {index} never arrived",
      )

  def test_deleting_a_path_outside_the_library_is_refused(self):
    self.session.send({"id": "del", "op": "delete", "filename": "../../app.json"})
    reply = self.session.wait_for(lambda message: message.get("id") == "del")

    self.assertEqual(reply["code"], "file_not_found")


if __name__ == "__main__":
  unittest.main()

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "micro" / "extractor"
sys.path.insert(0, str(ROOT))

from errors import classify_yt_dlp_error
from media import (
  classify_format,
  is_browser_playable,
  normalize_format,
  require_http_url,
  safe_filename,
)
from errors import ExtractorError
from engine import parse_progress_line, unique_path


class UrlValidationTests(unittest.TestCase):
  def test_accepts_https(self):
    self.assertEqual(
      require_http_url(" https://example.com/watch?v=1 "),
      "https://example.com/watch?v=1",
    )

  def test_rejects_javascript(self):
    with self.assertRaises(ExtractorError) as ctx:
      require_http_url("javascript:alert(1)")
    self.assertEqual(ctx.exception.code, "invalid_url")

  def test_rejects_credentials(self):
    with self.assertRaises(ExtractorError):
      require_http_url("https://user:pass@example.com/a")


class FilenameTests(unittest.TestCase):
  def test_strips_path_parts(self):
    name = safe_filename("../../etc/passwd", "mp4")
    self.assertEqual(name, "etc_passwd.mp4")

  def test_rejects_odd_extension(self):
    name = safe_filename("clip", "mp4;rm")
    self.assertTrue(name.endswith(".bin"))


class FormatTests(unittest.TestCase):
  def test_muxed_kind(self):
    self.assertEqual(
      classify_format({"vcodec": "avc1", "acodec": "mp4a"}),
      "muxed",
    )

  def test_skips_storyboard(self):
    self.assertIsNone(classify_format({"vcodec": "none", "acodec": "none"}))

  def test_playable_http_mp4(self):
    fmt = normalize_format({
      "format_id": "18",
      "vcodec": "avc1",
      "acodec": "mp4a",
      "ext": "mp4",
      "url": "https://cdn.example/video.mp4",
      "protocol": "https",
    })
    self.assertTrue(is_browser_playable(fmt))

  def test_hls_is_not_playable(self):
    fmt = normalize_format({
      "format_id": "91",
      "vcodec": "avc1",
      "acodec": "mp4a",
      "ext": "mp4",
      "url": "https://cdn.example/master.m3u8",
      "protocol": "m3u8_native",
    })
    self.assertFalse(fmt["playable"])


class ErrorClassificationTests(unittest.TestCase):
  def test_private(self):
    self.assertEqual(classify_yt_dlp_error("This video is private"), "private")

  def test_unsupported(self):
    self.assertEqual(classify_yt_dlp_error("Unsupported URL: ftp://x"), "unsupported_url")


class ProgressParseTests(unittest.TestCase):
  def test_percent_line(self):
    parsed = parse_progress_line(
      "[download]  12.3% of  10.00MiB at  1.20MiB/s ETA 00:08"
    )
    self.assertIsNotNone(parsed)
    self.assertAlmostEqual(parsed["percent"], 12.3)
    self.assertEqual(parsed["speed"], "1.20MiB/s")

  def test_ignores_other_lines(self):
    self.assertIsNone(parse_progress_line("[info] downloading"))


class UniquePathTests(unittest.TestCase):
  def test_increments(self):
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as folder:
      base = Path(folder) / "clip.mp4"
      base.write_bytes(b"a")
      next_path = unique_path(base)
      self.assertEqual(next_path.name, "clip-1.mp4")


if __name__ == "__main__":
  unittest.main()

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "micro" / "extractor"))

from errors import ExtractorError, classify_yt_dlp_failure, readable_failure
from media import (
  classify_track,
  optional_format_id,
  require_format_id,
  is_directly_playable,
  normalize_media,
  normalize_track,
  require_media_url,
  safe_extension,
  safe_filename_stem,
)


class UrlValidation(unittest.TestCase):
  def test_accepts_and_trims_an_https_url(self):
    self.assertEqual(
      require_media_url("  https://example.com/watch?v=1 "),
      "https://example.com/watch?v=1",
    )

  def test_rejects_a_non_http_scheme(self):
    with self.assertRaises(ExtractorError) as caught:
      require_media_url("javascript:alert(1)")

    self.assertEqual(caught.exception.code, "invalid_url")

  def test_rejects_a_file_url(self):
    with self.assertRaises(ExtractorError):
      require_media_url("file:///etc/passwd")

  def test_rejects_embedded_credentials(self):
    with self.assertRaises(ExtractorError):
      require_media_url("https://user:secret@example.com/a")

  def test_rejects_a_url_without_a_host(self):
    with self.assertRaises(ExtractorError):
      require_media_url("https:///nohost")

  def test_rejects_a_non_string(self):
    with self.assertRaises(ExtractorError):
      require_media_url(None)


class Filenames(unittest.TestCase):
  def test_strips_path_separators_from_a_title(self):
    self.assertEqual(safe_filename_stem("../../etc/passwd"), "etc_passwd")

  def test_keeps_ordinary_punctuation(self):
    self.assertEqual(
      safe_filename_stem("Artist - Song (Live) [2024]"),
      "Artist - Song (Live) [2024]",
    )

  def test_falls_back_when_nothing_usable_remains(self):
    self.assertEqual(safe_filename_stem("///"), "media")

  def test_truncates_a_very_long_title(self):
    self.assertEqual(len(safe_filename_stem("a" * 400)), 80)

  def test_rejects_an_implausible_extension(self):
    self.assertEqual(safe_extension("sh -c evil"), "bin")
    self.assertEqual(safe_extension(".MP4"), "mp4")


class FormatIdValidation(unittest.TestCase):
  def test_accepts_the_shape_of_a_real_format_id(self):
    for value in ("137", "mp4", "hls-1080", "dash_video.2", "251"):
      self.assertEqual(require_format_id(value), value)

  def test_rejects_a_yt_dlp_selector_expression(self):
    # --format takes an expression language; only a plain id may reach it.
    for value in ("bv+ba/b", "best[height<480]", "137/best", "bv*+ba"):
      with self.assertRaises(ExtractorError, msg=value):
        require_format_id(value)

  def test_rejects_whitespace_and_separators(self):
    for value in ("137 251", "../137", "a/b", "a;b", ""):
      with self.assertRaises(ExtractorError, msg=value):
        require_format_id(value)

  def test_rejects_an_overlong_id(self):
    with self.assertRaises(ExtractorError):
      require_format_id("a" * 200)

  def test_optional_id_allows_absence_but_still_validates(self):
    self.assertIsNone(optional_format_id(""))
    self.assertIsNone(optional_format_id(None))
    self.assertEqual(optional_format_id("140"), "140")

    with self.assertRaises(ExtractorError):
      optional_format_id("bv+ba")


class TrackClassification(unittest.TestCase):
  def test_known_codecs_classify_exactly(self):
    self.assertEqual(classify_track({"vcodec": "avc1", "acodec": "mp4a"}), ("muxed", True))
    self.assertEqual(classify_track({"vcodec": "avc1", "acodec": "none"}), ("video", True))
    self.assertEqual(classify_track({"vcodec": "none", "acodec": "mp4a"}), ("audio", True))

  def test_both_streams_absent_is_not_a_track(self):
    self.assertEqual(classify_track({"vcodec": "none", "acodec": "none"}), (None, True))

  def test_unknown_codecs_are_not_treated_as_absent(self):
    # yt-dlp reports null rather than "none" when it never found out. Reading
    # that as "no streams" is what made direct links look unsupported.
    kind, known = classify_track({"vcodec": None, "ext": "mp4"})

    self.assertEqual(kind, "muxed")
    self.assertFalse(known)

  def test_audio_container_without_codecs_is_audio(self):
    self.assertEqual(classify_track({"ext": "m4a"}), ("audio", False))

  def test_confirmed_video_with_unknown_audio_is_not_video_only(self):
    self.assertEqual(classify_track({"vcodec": "avc1"}), ("muxed", False))


class Playability(unittest.TestCase):
  def _track(self, **overrides):
    track = {
      "kind": "muxed",
      "ext": "mp4",
      "protocol": "https",
      "url": "https://cdn.example.com/a.mp4",
    }
    track.update(overrides)

    return track

  def test_a_progressive_mp4_is_playable(self):
    self.assertTrue(is_directly_playable(self._track()))

  def test_video_only_is_not_playable(self):
    self.assertFalse(is_directly_playable(self._track(kind="video")))

  def test_hls_is_not_playable(self):
    self.assertFalse(is_directly_playable(self._track(protocol="m3u8_native")))

  def test_an_unplayable_container_is_rejected(self):
    self.assertFalse(is_directly_playable(self._track(ext="mkv")))

  def test_a_non_http_url_is_rejected(self):
    self.assertFalse(is_directly_playable(self._track(url="data:video/mp4;base64,AA")))


class Normalization(unittest.TestCase):
  def test_a_track_without_a_format_id_is_dropped(self):
    self.assertIsNone(normalize_track({"vcodec": "avc1", "acodec": "mp4a"}))

  def test_formats_are_ordered_by_quality(self):
    media = normalize_media(
      {
        "title": "Example",
        "formats": [
          {"format_id": "low", "vcodec": "avc1", "acodec": "mp4a", "height": 360, "ext": "mp4"},
          {"format_id": "high", "vcodec": "avc1", "acodec": "mp4a", "height": 1080, "ext": "mp4"},
        ],
      },
      "https://example.com/v",
    )

    self.assertEqual([track["id"] for track in media["formats"]], ["high", "low"])

  def test_a_long_description_is_trimmed(self):
    media = normalize_media(
      {"title": "x", "description": "d" * 5000, "formats": []},
      "https://example.com/v",
    )

    self.assertLessEqual(len(media["description"]), 601)

  def test_the_format_count_is_capped(self):
    formats = [
      {"format_id": str(index), "vcodec": "avc1", "acodec": "mp4a", "height": index, "ext": "mp4"}
      for index in range(1, 400)
    ]

    media = normalize_media({"title": "x", "formats": formats}, "https://example.com/v")

    self.assertEqual(len(media["formats"]), 120)

  def test_missing_fields_do_not_raise(self):
    media = normalize_media({}, "https://example.com/v")

    self.assertEqual(media["title"], "Untitled")
    self.assertEqual(media["formats"], [])
    self.assertIsNone(media["durationSeconds"])


class FailureClassification(unittest.TestCase):
  def test_recognises_a_private_video(self):
    self.assertEqual(
      classify_yt_dlp_failure("ERROR: Private video. Sign in if you've been granted access"),
      "private_media",
    )

  def test_a_404_is_not_reported_as_a_network_problem(self):
    self.assertEqual(
      classify_yt_dlp_failure("ERROR: Unable to download webpage: HTTP Error 404: File not found"),
      "media_unavailable",
    )

  def test_recognises_an_unsupported_site(self):
    self.assertEqual(classify_yt_dlp_failure("ERROR: Unsupported URL: https://x.test"), "unsupported_site")

  def test_falls_back_for_unrecognised_text(self):
    self.assertEqual(classify_yt_dlp_failure("something else entirely"), "extractor_failure")

  def test_empty_text_is_handled(self):
    self.assertEqual(classify_yt_dlp_failure(""), "extractor_failure")

  def test_readable_failure_strips_the_error_prefix_and_progress_noise(self):
    self.assertEqual(
      readable_failure("[download]  10% of 1MiB\nERROR: Video unavailable"),
      "Video unavailable",
    )


if __name__ == "__main__":
  unittest.main()

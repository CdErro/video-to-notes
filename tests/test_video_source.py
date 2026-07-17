import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import video_source


class DetectPlatformTests(unittest.TestCase):
    def test_supported_urls(self):
        cases = {
            "https://www.youtube.com/watch?v=abc": "youtube",
            "https://youtu.be/abc": "youtube",
            "https://youtube.com/live/abc": "youtube",
            "https://youtube.com/shorts/abc": "youtube",
            "https://youtube.com/embed/abc": "youtube",
            "https://www.bilibili.com/video/BV1xx411c7mD": "bilibili",
            "https://b23.tv/abcdef": "bilibili",
            "https://x.com/person/status/2075594420163092606": "x",
            "https://x.com/person/status/2075594420163092606/video/1": "x",
            "https://mobile.twitter.com/person/status/2075594420163092606?x=1#fragment": "x",
            "https://xhslink.com/aBcD": "xiaohongshu",
            "https://www.xiaohongshu.com/explore/64a1bc2d": "xiaohongshu",
            "https://www.xiaohongshu.com/discovery/item/64A1bc2D": "xiaohongshu",
        }

        for url, expected in cases.items():
            with self.subTest(url=url):
                self.assertEqual(video_source.detect_platform(url), expected)

    def test_unsupported_urls(self):
        cases = (
            "https://youtube.com/",
            "https://youtube.com/channel/teacher",
            "https://youtube.com/watch",
            "https://youtube.com/watch?v=",
            "https://youtube.com/arbitrary/path",
            "https://youtu.be/",
            "https://x.com/",
            "https://x.com/person",
            "https://t.co/abc",
            "not-a-url",
            "ftp://x.com/person/status/123",
            "http://[::1",
            "https://x.com:bad/person/status/123",
            "https://x.com/person/status/１２３",
            "https://x.com/person/status/123/video/١",
            "https://xhslink.com/",
            "https://www.xiaohongshu.com/user/profile/123",
        )

        for url in cases:
            with self.subTest(url=url):
                with self.assertRaises(video_source.UnsupportedSourceError):
                    video_source.detect_platform(url)

    def test_youtube_video_ids_are_ascii_and_have_no_extra_segments(self):
        cases = (
            "https://youtu.be/abc/extra",
            "https://youtu.be/视频",
            "https://youtube.com/live/abc/extra",
            "https://youtube.com/shorts/视频",
            "https://youtube.com/embed/abc/extra",
            "https://youtube.com/watch?v=视频",
            "https://youtube.com/watch?v=abc%2Fextra",
        )

        for url in cases:
            with self.subTest(url=url):
                with self.assertRaises(video_source.UnsupportedSourceError):
                    video_source.detect_platform(url)


class ProbeTests(unittest.TestCase):
    URL = "https://x.com/person/status/2075594420163092606/video/1"

    @mock.patch("video_source.subprocess.run")
    def test_probe_returns_compact_metadata(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    "id": "2075594420163092606",
                    "title": "Lecture",
                    "uploader": "Teacher",
                    "duration": 120.5,
                    "webpage_url": self.URL,
                    "thumbnail": "https://example.test/thumb.jpg",
                    "subtitles": {"en": [{}]},
                    "automatic_captions": {"zh": [{}]},
                }
            ),
            stderr="",
        )

        result = video_source.probe_source(self.URL)

        self.assertEqual(result["platform"], "x")
        self.assertEqual(result["id"], "2075594420163092606")
        self.assertEqual(result["subtitle_languages"], ["en", "zh"])
        self.assertTrue(result["has_thumbnail"])
        run.assert_called_once_with(
            [
                "yt-dlp",
                "--dump-single-json",
                "--no-playlist",
                "--skip-download",
                self.URL,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    @mock.patch("video_source.subprocess.run")
    def test_probe_rejects_extractor_failure(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="private post"
        )

        with self.assertRaisesRegex(video_source.ProbeError, "private post"):
            video_source.probe_source(self.URL)

    @mock.patch("video_source.subprocess.run")
    def test_probe_rejects_missing_id_or_invalid_duration(self, run):
        payloads = (
            {"duration": 1},
            {"id": "123", "duration": 0},
            {"id": "123", "duration": -1},
            {"id": "123", "duration": True},
        )

        for payload in payloads:
            with self.subTest(payload=payload):
                run.return_value = subprocess.CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout=json.dumps(payload),
                    stderr="",
                )
                with self.assertRaises(video_source.ProbeError):
                    video_source.probe_source(self.URL)

    @mock.patch("video_source.subprocess.run")
    def test_probe_rejects_non_object_metadata(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps([]), stderr=""
        )

        with self.assertRaisesRegex(video_source.ProbeError, "JSON object"):
            video_source.probe_source(self.URL)

    @mock.patch("video_source.subprocess.run")
    def test_probe_rejects_non_mapping_subtitles(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"id": "123", "duration": 1, "subtitles": []}),
            stderr="",
        )

        with self.assertRaisesRegex(video_source.ProbeError, "subtitles"):
            video_source.probe_source(self.URL)

    @mock.patch("video_source.subprocess.run")
    def test_probe_rejects_non_mapping_automatic_captions(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {"id": "123", "duration": 1, "automatic_captions": "zh"}
            ),
            stderr="",
        )

        with self.assertRaisesRegex(video_source.ProbeError, "automatic_captions"):
            video_source.probe_source(self.URL)

    @mock.patch("video_source.subprocess.run")
    def test_probe_rejects_non_finite_duration(self, run):
        for duration in (float("nan"), float("inf")):
            with self.subTest(duration=duration):
                run.return_value = subprocess.CompletedProcess(
                    args=[],
                    returncode=0,
                    stdout=json.dumps({"id": "123", "duration": duration}),
                    stderr="",
                )
                with self.assertRaises(video_source.ProbeError):
                    video_source.probe_source(self.URL)

    @mock.patch("video_source.subprocess.run")
    def test_probe_rejects_invalid_json(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="not JSON", stderr=""
        )

        with self.assertRaisesRegex(video_source.ProbeError, "invalid JSON metadata"):
            video_source.probe_source(self.URL)

    @mock.patch("video_source.subprocess.run", side_effect=FileNotFoundError)
    def test_probe_reports_missing_ytdlp(self, run):
        with self.assertRaisesRegex(video_source.ProbeError, "yt-dlp"):
            video_source.probe_source(self.URL)


class XiaohongshuTests(unittest.TestCase):
    SHORT_URL = "https://xhslink.com/AbCd"
    CANONICAL_URL = "https://www.xiaohongshu.com/explore/64a1bc2d"

    @mock.patch("video_source._redirect_location")
    def test_short_link_resolves_only_to_official_video_page(self, redirect):
        redirect.return_value = self.CANONICAL_URL + "?xsec_token=secret#comment"

        self.assertEqual(
            video_source.resolve_xiaohongshu_url(self.SHORT_URL),
            self.CANONICAL_URL,
        )

    @mock.patch("video_source._redirect_location")
    def test_short_link_rejects_external_redirect(self, redirect):
        redirect.return_value = "https://example.com/steal"

        with self.assertRaisesRegex(video_source.ProbeError, "非官方域名"):
            video_source.resolve_xiaohongshu_url(self.SHORT_URL)

    @mock.patch("video_source.subprocess.run")
    def test_probe_records_urls_and_uses_browser_cookies(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    "id": "64a1bc2d",
                    "title": "视频笔记",
                    "duration": 12,
                    "webpage_url": self.CANONICAL_URL,
                    "formats": [{"url": "https://media.example/video.mp4"}],
                }
            ),
            stderr="",
        )

        result = video_source.probe_source(
            self.CANONICAL_URL, cookies_from_browser="chrome"
        )

        self.assertEqual(result["original_url"], self.CANONICAL_URL)
        self.assertEqual(result["canonical_url"], self.CANONICAL_URL)
        self.assertIn("--cookies-from-browser", run.call_args.args[0])
        self.assertNotIn("secret", json.dumps(result))

    @mock.patch("video_source.subprocess.run")
    def test_probe_rejects_image_only_note(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {"id": "64a1bc2d", "title": "图文", "duration": 1, "formats": []}
            ),
            stderr="",
        )

        with self.assertRaisesRegex(video_source.ProbeError, "纯图文"):
            video_source.probe_source(self.CANONICAL_URL)

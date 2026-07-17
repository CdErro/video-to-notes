import argparse
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import video_to_notes
from llm_provider import ProviderError


class FakeProvider:
    name = "fake"
    model = "test"

    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = 0

    def generate(self, prompt, images, schema):
        self.calls += 1
        result = next(self.responses)
        if isinstance(result, Exception):
            raise result
        return result


def healthy_srt(duration=100):
    return (
        "1\n00:00:09,000 --> 00:00:12,000\n开始内容\n\n"
        "2\n00:00:49,000 --> 00:00:52,000\n中间内容\n\n"
        f"3\n00:01:29,000 --> 00:01:{duration - 60:02d},000\n结束内容\n"
    )


class PipelineUnitTests(unittest.TestCase):
    def test_default_kimi_model_is_not_highspeed(self):
        self.assertEqual(
            "kimi-code/kimi-for-coding",
            video_to_notes.provider_model("kimi-cli", ""),
        )
        self.assertEqual("custom", video_to_notes.provider_model("kimi-cli", "custom"))

    def test_query_tokens_are_not_persisted(self):
        self.assertEqual(
            "https://www.xiaohongshu.com/explore/abc",
            video_to_notes.safe_url("https://www.xiaohongshu.com/explore/abc?xsec_token=secret"),
        )

    def test_noninteractive_visual_fallback_requires_explicit_flag(self):
        self.assertFalse(video_to_notes.visual_fallback_allowed(False, False))
        self.assertTrue(video_to_notes.visual_fallback_allowed(True, False))

    def test_select_caption_rejects_unhealthy_and_prefers_healthy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bad = root / "video.zh.srt"
            good = root / "video.en.srt"
            bad.write_text("1\n00:00:00,000 --> 00:00:01,000\n短\n", encoding="utf-8")
            good.write_text(healthy_srt(), encoding="utf-8")
            selected = video_to_notes.select_caption([bad, good], 100)
        self.assertEqual(good, selected)

    @mock.patch("video_to_notes.subprocess.run")
    def test_download_reads_browser_cookies_without_cookie_file(self, run):
        def completed(command, **_kwargs):
            source = Path(command[command.index("-o") + 1]).parent
            (source / "video.mp4").touch()
            return subprocess.CompletedProcess(command, 0, "", "")

        run.side_effect = completed
        with tempfile.TemporaryDirectory() as directory:
            video_to_notes.download_source("https://example.test/video", Path(directory), "chrome")
        command = run.call_args.args[0]
        self.assertIn("--cookies-from-browser", command)
        self.assertNotIn("--cookies", command)

    def test_note_generation_retries_without_switching_provider(self):
        provider = FakeProvider([
            ProviderError("bad"), ProviderError("bad"),
            {"title": "标题", "sections": [{"heading": "一", "body": "正文", "timestamp": 0}], "figures": [], "source_signals": []},
        ])
        result = video_to_notes.generate_notes_payload(provider, "prompt", [])
        self.assertEqual("标题", result["title"])
        self.assertEqual(3, provider.calls)

    def test_fallback_meets_short_markdown_shape(self):
        payload = video_to_notes.fallback_payload(healthy_srt(), 100, "标题")
        markdown = video_to_notes.payload_to_markdown(payload, [])
        self.assertGreaterEqual(markdown.count("## "), 2)
        self.assertIn("00:00:09", markdown)


class PipelineIntegrationTests(unittest.TestCase):
    def test_execute_records_stages_and_single_frame_figures(self):
        payload = {
            "title": "测试笔记",
            "sections": [
                {"heading": "第一节", "body": "这是第一节的完整中文内容，用于说明视频中的主要观点和具体证据。", "timestamp": 9},
                {"heading": "第二节", "body": "这是第二节的完整中文内容，用于说明视频中的后续观点和实际结论。", "timestamp": 49},
            ],
            "figures": [{"timestamp": 9, "section": "第一节", "caption": "单帧证据"}],
            "source_signals": ["figure"],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "run"
            source = root / "download.mp4"
            caption = root / "download.zh.srt"
            source.touch()
            caption.write_text(healthy_srt(), encoding="utf-8")
            args = argparse.Namespace(
                url="https://www.xiaohongshu.com/explore/abc?xsec_token=secret",
                provider="kimi-cli", model="", env_file=root / ".env", provider_timeout=180,
                config=root / "config.toml", domain=None, context=None,
                format="markdown", cookies_from_browser=None, whisper_model=None,
                output_dir=output, resume=False, allow_visual_only=False,
            )

            def samples(_video, target, _duration, _interval, _ffmpeg):
                frames = target / "evidence/frames"
                frames.mkdir(parents=True)
                (frames / "frame_0001.jpg").touch()
                manifest = target / "evidence/frame_manifest.tsv"
                manifest.write_text("frame\ttimestamp\nframe_0001.jpg\t9.000\n", encoding="utf-8")
                return [{"frame": "frame_0001.jpg", "timestamp": 9.0}]

            def figures(_video, target, candidates, _ffmpeg):
                path = target / "figures/figure_001.jpg"
                path.parent.mkdir(parents=True)
                path.touch()
                records = [{"path": "figures/figure_001.jpg", **candidates[0]}]
                (target / "figure_manifest.json").write_text(json.dumps({"figures": records}), encoding="utf-8")
                return records

            manifest = {"outputs": {"notes.md": {"status": "ready"}}, "degraded": False, "degradation_reasons": []}
            with mock.patch.multiple(
                video_to_notes,
                required_environment=mock.DEFAULT,
                probe_source=mock.DEFAULT,
                download_source=mock.DEFAULT,
                extract_sample_frames=mock.DEFAULT,
                create_contact_sheets=mock.DEFAULT,
                semantic_correction=mock.DEFAULT,
                create_provider=mock.DEFAULT,
                generate_notes_payload=mock.DEFAULT,
                materialize_figures=mock.DEFAULT,
                render=mock.DEFAULT,
            ) as patched:
                patched["probe_source"].return_value = {"platform": "xiaohongshu", "id": "abc", "title": "测试", "duration": 100.0, "webpage_url": args.url}
                patched["download_source"].return_value = (source, [caption])
                patched["extract_sample_frames"].side_effect = samples
                contact = output / "evidence/contact_sheets/contact_001.jpg"
                patched["create_contact_sheets"].return_value = [contact]
                patched["semantic_correction"].side_effect = lambda src, out, *_args: (out.write_bytes(src.read_bytes()) or True)
                patched["generate_notes_payload"].return_value = payload
                patched["materialize_figures"].side_effect = figures
                patched["render"].return_value = (0, manifest)
                result = video_to_notes.execute(args)

            state = json.loads((output / "pipeline_state.json").read_text(encoding="utf-8"))
            final_manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
            notes = (output / "draft.md").read_text(encoding="utf-8")

        self.assertEqual(output, result)
        self.assertEqual("completed", state["stages"]["render"]["status"])
        self.assertIn("transcription", final_manifest)
        self.assertNotIn("secret", json.dumps(final_manifest))
        self.assertIn("figures/figure_001.jpg", notes)
        self.assertNotIn("contact_001.jpg", notes)


if __name__ == "__main__":
    unittest.main()

import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import llm_correct_srt
from llm_provider import ProviderError


class FakeProvider:
    name = "fake"
    model = "test"

    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = 0

    def correct(self, prompt, image, schema):
        self.calls += 1
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


class FrameSelectionTests(unittest.TestCase):
    def test_manifest_supplies_absolute_timestamps(self):
        with tempfile.TemporaryDirectory() as directory:
            frames = Path(directory)
            (frames / "ch2_001.png").touch()
            (frames / "ch2_002.png").touch()
            manifest_path = frames / "manifest.tsv"
            manifest_path.write_text(
                "frame\tstart\nch2_001.png\t2700\nch2_002.png\t2715\n",
                encoding="utf-8",
            )

            manifest = llm_correct_srt.load_frame_manifest(manifest_path)
            selected = llm_correct_srt.pick_frame(frames, 2714, manifest)

        self.assertEqual("ch2_002.png", selected.name)

    def test_manifest_selects_jpeg_evidence_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            frames = Path(directory)
            (frames / "frame_0001.jpg").touch()
            (frames / "frame_0002.jpg").touch()

            selected = llm_correct_srt.pick_frame(
                frames, 14, {"frame_0001.jpg": 0, "frame_0002.jpg": 15}
            )

        self.assertEqual("frame_0002.jpg", selected.name)


class CorrectionTests(unittest.TestCase):
    def test_retries_invalid_output_then_accepts_complete_segment(self):
        entries = [
            llm_correct_srt.SrtEntry(1, 0, 1, "错字"),
            llm_correct_srt.SrtEntry(2, 1, 2, "原文"),
        ]
        provider = FakeProvider(
            [
                {"corrections": [{"index": 1, "text": "正确"}]},
                {
                    "corrections": [
                        {"index": 1, "text": "正确"},
                        {"index": 2, "text": "原文"},
                    ],
                    "glossary_candidates": [],
                },
            ]
        )
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "llm_correct_srt.time.sleep"
        ):
            corrections, _, _, _, _ = llm_correct_srt.correct_segment(
                entries, None, "general", Path(directory), provider
            )

        self.assertEqual({1: "正确", 2: "原文"}, corrections)
        self.assertEqual(2, provider.calls)

    def test_three_failures_degrade_to_original(self):
        entry = llm_correct_srt.SrtEntry(1, 0, 1, "保留")
        provider = FakeProvider([ProviderError("bad")] * 3)
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "llm_correct_srt.time.sleep"
        ):
            corrections, _, _, _, _ = llm_correct_srt.correct_segment(
                [entry], None, "general", Path(directory), provider
            )

        self.assertEqual({}, corrections)
        self.assertEqual(3, provider.calls)

    def test_cache_changes_when_subtitle_text_changes(self):
        provider = FakeProvider(
            [
                {
                    "corrections": [{"index": 1, "text": "first-fixed"}],
                    "glossary_candidates": [],
                },
                {
                    "corrections": [{"index": 1, "text": "second-fixed"}],
                    "glossary_candidates": [],
                },
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            first = [llm_correct_srt.SrtEntry(1, 0, 1, "first")]
            second = [llm_correct_srt.SrtEntry(1, 0, 1, "second")]

            llm_correct_srt.correct_segment(first, None, "general", cache, provider)
            result, _, _, was_cached, _ = llm_correct_srt.correct_segment(
                second, None, "general", cache, provider
            )

        self.assertEqual({1: "second-fixed"}, result)
        self.assertFalse(was_cached)
        self.assertEqual(2, provider.calls)

    def test_cli_provider_initialization_failure_is_nonzero(self):
        with tempfile.TemporaryDirectory() as directory:
            srt = Path(directory) / "audio.srt"
            srt.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\ntext\n", encoding="utf-8"
            )
            environment = os.environ.copy()
            environment.pop("OPENAI_API_KEY", None)
            environment.pop("OPNEAI_API_KEY", None)
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "llm_correct_srt.py"),
                    "--srt",
                    str(srt),
                    "--out",
                    str(Path(directory) / "out.srt"),
                    "--context",
                    "general",
                    "--provider",
                    "openai",
                    "--env-file",
                    str(Path(directory) / "missing.env"),
                ],
                capture_output=True,
                text=True,
                env=environment,
                check=False,
            )

        self.assertEqual(2, result.returncode)
        self.assertIn("OPENAI_API_KEY", result.stderr)

    def test_successful_run_updates_evidenced_glossary(self):
        provider = FakeProvider(
            [
                {
                    "corrections": [{"index": 1, "text": "使用 Python"}],
                    "glossary_candidates": [
                        {"original": "派散", "corrected": "Python", "indices": [1]}
                    ],
                }
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "audio.srt"
            output = root / "corrected.srt"
            source.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\n使用派散\n", encoding="utf-8"
            )
            argv = [
                "llm_correct_srt.py",
                "--srt",
                str(source),
                "--out",
                str(output),
                "--context",
                "通用视频",
                "--glossary-root",
                str(root / "glossaries"),
            ]
            with mock.patch.object(sys, "argv", argv), mock.patch(
                "llm_correct_srt.create_provider", return_value=provider
            ), redirect_stdout(StringIO()):
                result = llm_correct_srt.main()

            saved = (root / "glossaries" / "general.json").read_text(encoding="utf-8")
            audit_exists = (root / "glossary_update.json").exists()

        self.assertEqual(0, result)
        self.assertIn("派散", saved)
        self.assertTrue(audit_exists)


if __name__ == "__main__":
    unittest.main()

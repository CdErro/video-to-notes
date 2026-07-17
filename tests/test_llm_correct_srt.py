import sys
import tempfile
import unittest
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
                    ]
                },
            ]
        )
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "llm_correct_srt.time.sleep"
        ):
            corrections, _, _, _ = llm_correct_srt.correct_segment(
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
            corrections, _, _, _ = llm_correct_srt.correct_segment(
                [entry], None, "general", Path(directory), provider
            )

        self.assertEqual({}, corrections)
        self.assertEqual(3, provider.calls)


if __name__ == "__main__":
    unittest.main()

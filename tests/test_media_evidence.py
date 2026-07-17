import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import media_evidence


class MediaEvidenceTests(unittest.TestCase):
    @mock.patch("media_evidence.subprocess.run")
    def test_sample_frames_write_timestamp_manifest(self, run):
        def create_frame(command, **_kwargs):
            Path(command[-1]).touch()
            return subprocess.CompletedProcess(command, 0, "", "")

        run.side_effect = create_frame
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records = media_evidence.extract_sample_frames(
                root / "video.mp4", root / "run", 31, 15, "ffmpeg"
            )
            manifest = (root / "run/evidence/frame_manifest.tsv").read_text()

        self.assertEqual([0.0, 15.0, 30.0], [item["timestamp"] for item in records])
        self.assertIn("frame_0002.jpg\t15.000", manifest)

    @mock.patch("media_evidence.subprocess.run")
    def test_figures_are_single_frames_with_section_mapping(self, run):
        def create_frame(command, **_kwargs):
            Path(command[-1]).touch()
            return subprocess.CompletedProcess(command, 0, "", "")

        run.side_effect = create_frame
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records = media_evidence.materialize_figures(
                root / "video.mp4", root / "run",
                [{"timestamp": 12.5, "section": "核心", "caption": "界面"}], "ffmpeg",
            )
            saved = json.loads((root / "run/figure_manifest.json").read_text())

        self.assertEqual("figures/figure_001.jpg", records[0]["path"])
        self.assertEqual("核心", saved["figures"][0]["section"])

    @mock.patch("media_evidence.subprocess.run")
    def test_ffmpeg_failure_is_actionable(self, run):
        run.return_value = subprocess.CompletedProcess([], 1, "", "decode failed")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(media_evidence.EvidenceError, "decode failed"):
                media_evidence.materialize_figures(
                    Path(directory) / "video.mp4", Path(directory) / "run",
                    [{"timestamp": 1}], "ffmpeg",
                )


if __name__ == "__main__":
    unittest.main()

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import correct_srt


class CorrectSrtTests(unittest.TestCase):
    def test_cli_uses_general_plus_requested_domain(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "audio.srt"
            source.write_text(
                "1\n00:00:00,000 --> 00:00:01,000\n佛克\n", encoding="utf-8"
            )
            argv = [
                "correct_srt.py",
                str(source),
                "--domain",
                "nju-os",
                "--glossary-root",
                str(Path(directory) / "user"),
            ]
            with mock.patch.object(sys, "argv", argv):
                correct_srt.main()

            result = source.read_text(encoding="utf-8")

        self.assertIn("fork", result)


if __name__ == "__main__":
    unittest.main()

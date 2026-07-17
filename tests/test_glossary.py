import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import glossary


class GlossaryTests(unittest.TestCase):
    def test_detects_nju_os_but_always_keeps_general(self):
        self.assertEqual(["general"], glossary.detect_domains("烹饪入门"))
        self.assertEqual(
            ["general", "nju-os"],
            glossary.detect_domains("南京大学操作系统课程讲解 fork 与 kernel"),
        )

    def test_nju_os_seed_is_optional(self):
        general = glossary.replacements(["general"], Path("missing-user-root"))
        nju = glossary.replacements(["general", "nju-os"], Path("missing-user-root"))

        self.assertNotIn("佛克", general)
        self.assertEqual("fork", nju["佛克"])

    def test_updates_only_with_matching_srt_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit = glossary.update_glossary(
                {1: "使用派散处理", 2: "其他内容"},
                {1: "使用 Python 处理", 2: "其他内容"},
                [
                    {"original": "派散", "corrected": "Python", "indices": [1]},
                    {"original": "无证据", "corrected": "wrong", "indices": [2]},
                ],
                "general",
                root,
                root / "audit.json",
            )

            saved = json.loads((root / "general.json").read_text(encoding="utf-8"))

        self.assertIn("派散", saved["entries"])
        self.assertEqual(1, len(audit["added"]))
        self.assertEqual("evidence_mismatch", audit["rejected"][0]["reason"])

    def test_conflict_never_overwrites_existing_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "general.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "domain": "general",
                        "entries": {"派散": {"replacement": "Python", "evidence": []}},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            audit = glossary.update_glossary(
                {1: "派散"},
                {1: "PyTorch"},
                [{"original": "派散", "corrected": "PyTorch", "indices": [1]}],
                "general",
                root,
            )
            saved = json.loads((root / "general.json").read_text(encoding="utf-8"))

        self.assertEqual("Python", saved["entries"]["派散"]["replacement"])
        self.assertEqual(1, len(audit["conflicts"]))

    def test_duplicate_normalization_is_not_readded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            glossary.update_glossary(
                {1: "Ｐｙｔｈｏｎ"},
                {1: "Python"},
                [{"original": "Ｐｙｔｈｏｎ", "corrected": "Python", "indices": [1]}],
                "general",
                root,
            )
            second = glossary.update_glossary(
                {2: "python"},
                {2: "Python"},
                [{"original": "python", "corrected": "Python", "indices": [2]}],
                "general",
                root,
            )

        self.assertEqual([], second["added"])


if __name__ == "__main__":
    unittest.main()

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills" / "video-to-notes"


class VideoToNotesSkillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        cls.legacy = (ROOT / "skills" / "lecture-to-notes" / "SKILL.md").read_text(
            encoding="utf-8"
        )

    def test_skill_has_no_scaffold_placeholders(self):
        self.assertNotIn("TODO", self.skill)
        self.assertTrue((SKILL_ROOT / "agents" / "openai.yaml").is_file())
        self.assertTrue((SKILL_ROOT / "references" / "quality-rules.md").is_file())
        self.assertTrue((SKILL_ROOT / "assets" / "notes-outline.md").is_file())

    def test_skill_requires_markdown_manifest_and_conditional_evidence(self):
        self.assertIn("Always deliver Markdown", self.skill)
        self.assertIn("run_manifest.json", self.skill)
        for signal in ("formula", "code", "table", "figure"):
            self.assertIn(signal, self.skill)

    def test_repository_root_resolution_names_required_directories(self):
        self.assertIn("nearest ancestor", self.skill)
        for directory in ("`scripts/`", "`skills/`", "`tests/`"):
            self.assertIn(directory, self.skill)
        self.assertNotIn("two levels above", self.skill)

    def test_legacy_entry_points_to_current_skill(self):
        self.assertIn("use the `video-to-notes` skill for new requests", self.legacy)


if __name__ == "__main__":
    unittest.main()

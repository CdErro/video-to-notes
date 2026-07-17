import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import render_notes


def valid_short_notes() -> str:
    chinese = "这是来自视频内容的中文解释，保留机制、结论和来源证据。" * 4
    return f"# 示例笔记\n\n## 核心概念\n\n{chinese} 00:10\n\n## 总结\n\n{chinese}\n"


class RenderNotesTests(unittest.TestCase):
    def test_duration_boundaries_select_three_quality_tiers(self):
        self.assertEqual("short", render_notes.quality_rule(299.9).name)
        self.assertEqual("standard", render_notes.quality_rule(300).name)
        self.assertEqual("standard", render_notes.quality_rule(1799.9).name)
        self.assertEqual("long", render_notes.quality_rule(1800).name)

    def test_markdown_is_always_written_with_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "draft.md"
            source.write_text(valid_short_notes(), encoding="utf-8")

            code, manifest = render_notes.render(
                source, root / "run", "markdown", 120, "xiaohongshu", "general", "none", set()
            )

            saved = json.loads((root / "run" / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(0, code)
            self.assertTrue((root / "run" / "notes.md").is_file())
            self.assertEqual("xiaohongshu", saved["platform"])
            self.assertFalse(manifest["degraded"])

    def test_quality_failure_keeps_markdown_and_records_degradation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "draft.md"
            source.write_text("# 太短\n", encoding="utf-8")

            code, manifest = render_notes.render(
                source, root / "run", "pdf", 60, "youtube", "general", "kimi-cli", set()
            )

        self.assertEqual(2, code)
        self.assertTrue(manifest["degraded"])
        self.assertIn("notes.md", manifest["outputs"])

    @mock.patch("render_notes.subprocess.run")
    @mock.patch("render_notes.shutil.which")
    def test_pdf_uses_pandoc_and_xelatex(self, which, run):
        which.side_effect = lambda command: f"/tools/{command}"
        def create_output(command, **_kwargs):
            Path(command[command.index("-o") + 1]).touch()
            return subprocess.CompletedProcess([], 0, "", "")

        run.side_effect = create_output
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "draft.md"
            source.write_text(valid_short_notes(), encoding="utf-8")

            code, manifest = render_notes.render(
                source, root / "run", "pdf", 120, "bilibili", "general", "openai", set()
            )

        self.assertEqual(0, code)
        command = run.call_args.args[0]
        self.assertIn("--pdf-engine=xelatex", command)
        self.assertEqual("ready", manifest["outputs"]["notes.pdf"]["status"])

    def test_source_signal_requires_matching_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "draft.md"
            source.write_text(valid_short_notes(), encoding="utf-8")

            _, issues = render_notes.assess_notes(
                source.read_text(encoding="utf-8"), 120, {"code"}, root
            )

        self.assertIn("Source contains code, but notes.md does not", issues)

    def test_contact_sheet_is_rejected_as_final_figure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            text = valid_short_notes() + "\n![分析拼图](contact_01.jpg)\n"
            _, issues = render_notes.assess_notes(text, 120, {"figure"}, root)

        self.assertIn(
            "Contact sheets are analysis artifacts and cannot be embedded in notes.md",
            issues,
        )

    def test_single_frame_figure_and_mapping_enter_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "draft.md"
            source.write_text(
                valid_short_notes() + "\n![界面](figures/figure_001.jpg)\n",
                encoding="utf-8",
            )
            (root / "figure_manifest.json").write_text(
                json.dumps({"figures": [{"path": "figures/figure_001.jpg", "timestamp": 8}]}),
                encoding="utf-8",
            )
            code, manifest = render_notes.render(
                source, root, "markdown", 120, "xiaohongshu", "general", "none", {"figure"}
            )

        self.assertEqual(0, code)
        self.assertEqual(8, manifest["figures"][0]["timestamp"])

    def test_invalid_figure_manifest_marks_run_degraded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "draft.md"
            source.write_text(valid_short_notes(), encoding="utf-8")
            (root / "figure_manifest.json").write_text("[]", encoding="utf-8")

            code, manifest = render_notes.render(
                source, root, "markdown", 120, "youtube", "general", "none", set()
            )

        self.assertEqual(2, code)
        self.assertTrue(manifest["degraded"])
        self.assertIn("figure_manifest.json is invalid", manifest["degradation_reasons"])

    def test_missing_pdf_tools_are_recorded_as_unavailable(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "render_notes.shutil.which", return_value=None
        ):
            root = Path(directory)
            source = root / "draft.md"
            source.write_text(valid_short_notes(), encoding="utf-8")

            code, manifest = render_notes.render(
                source, root / "run", "pdf", 120, "youtube", "general", "none", set()
            )

        self.assertEqual(1, code)
        self.assertEqual("unavailable", manifest["outputs"]["notes.pdf"]["status"])


if __name__ == "__main__":
    unittest.main()

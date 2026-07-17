import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import environment


class EnvironmentDoctorTests(unittest.TestCase):
    def test_markdown_kimi_profile_marks_expected_dependencies_required(self):
        required = environment.required_names("markdown", "kimi-cli")

        self.assertIn("FFmpeg", required)
        self.assertIn("Kimi Code CLI", required)
        self.assertNotIn("Pandoc", required)
        self.assertNotIn("OPENAI_API_KEY", required)

    def test_pdf_openai_profile_requires_renderer_and_credential(self):
        required = environment.required_names("pdf", "openai")

        self.assertTrue({"Pandoc", "XeLaTeX", "openai", "OPENAI_API_KEY"} <= required)
        self.assertNotIn("Kimi Code CLI", required)

    @mock.patch("environment.shutil.which", return_value=None)
    def test_missing_required_command_is_reported(self, _which):
        results = environment.check_commands({"FFmpeg"}, {})
        ffmpeg = next(item for item in results if item.name == "FFmpeg")

        self.assertEqual("required_missing", ffmpeg.status)
        self.assertTrue(ffmpeg.required)

    @mock.patch("environment.subprocess.run")
    def test_configured_command_is_executed(self, run):
        run.return_value = mock.Mock(returncode=0, stdout="ffmpeg version 8.1\n", stderr="")

        results = environment.check_commands(set(), {"ffmpeg": "C:/tools/ffmpeg.exe"})
        ffmpeg = next(item for item in results if item.name == "FFmpeg")

        self.assertEqual("ready", ffmpeg.status)
        self.assertEqual("C:/tools/ffmpeg.exe", ffmpeg.path)
        run.assert_any_call(
            ["C:/tools/ffmpeg.exe", "-version"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

    def test_openai_key_check_does_not_expose_value(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "secret-value"}):
            result = environment.check_credentials({"OPENAI_API_KEY"})[0]

        self.assertEqual("ready", result.status)
        self.assertEqual("set", result.detail)
        self.assertNotIn("secret-value", str(result))

    @mock.patch("environment.importlib.metadata.version", return_value="2.43.0")
    @mock.patch("environment.importlib.util.find_spec", return_value=object())
    def test_unsupported_python_package_version_is_reported(self, _spec, _version):
        openai = next(item for item in environment.check_python({"openai"}) if item.name == "openai")

        self.assertEqual("version_unsupported", openai.status)


class EnvironmentInstallTests(unittest.TestCase):
    @mock.patch("environment.target_python")
    def test_installation_is_idempotent_when_everything_is_ready(self, target_python):
        target_python.return_value = (["python"], [])
        ready = [environment.CheckResult("FFmpeg", "command", "ready", True, "ok")]

        self.assertEqual([], environment.installation_commands(ready, "conda:vid2rich"))

    @mock.patch("environment.target_python")
    def test_missing_python_package_uses_target_interpreter(self, target_python):
        target_python.return_value = (["conda", "run", "-n", "vid2rich", "python"], [])
        missing = [environment.CheckResult("openai", "python_package", "required_missing", True, "missing")]

        commands = environment.installation_commands(missing, "conda:vid2rich")

        self.assertEqual("conda", commands[0][0])
        self.assertIn(str(environment.REQUIREMENTS_PATH), commands[0])

    @mock.patch("environment.target_python")
    def test_optional_python_package_is_not_installed(self, target_python):
        target_python.return_value = (["python"], [])
        missing = [
            environment.CheckResult(
                "Torch", "python_package", "optional_missing", False, "missing"
            )
        ]

        self.assertEqual([], environment.installation_commands(missing, "venv:.venv"))

    @mock.patch("environment.shutil.which", return_value=None)
    def test_missing_package_manager_returns_manual_guidance(self, _which):
        missing = [
            environment.CheckResult(
                "FFmpeg", "command", "required_missing", True, "not found"
            )
        ]

        guidance = environment.manual_install_guidance(missing)

        self.assertEqual(1, len(guidance))
        self.assertIn("ffmpeg.org", guidance[0])

    def test_windows_setup_falls_back_to_venv(self):
        setup = (environment.ROOT / "setup.ps1").read_text(encoding="utf-8")

        self.assertIn('$Target = "venv:.venv"', setup)

    def test_json_report_is_machine_readable(self):
        result = environment.CheckResult("Python", "runtime", "ready", True, "3.13")
        with mock.patch("builtins.print") as printer:
            environment.print_report([result], as_json=True)

        payload = json.loads(printer.call_args.args[0])
        self.assertEqual("ready", payload["checks"][0]["status"])


if __name__ == "__main__":
    unittest.main()

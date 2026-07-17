import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import llm_provider


SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
}


class DotenvTests(unittest.TestCase):
    def test_loads_supported_names_without_overriding_process(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(
                "OPENAI_BASE_URL=https://proxy.example/v1\n"
                "OPENAI_API_KEY=file-key\nOPNEAI_API_KEY=typo-key\n",
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "process-key"}, clear=True):
                llm_provider.load_dotenv(path)
                self.assertEqual("process-key", os.environ["OPENAI_API_KEY"])
                self.assertEqual("https://proxy.example/v1", os.environ["OPENAI_BASE_URL"])
                self.assertNotIn("OPNEAI_API_KEY", os.environ)


class KimiProviderTests(unittest.TestCase):
    @mock.patch("llm_provider.subprocess.run")
    def test_parses_final_json_from_stream_json(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=(
                json.dumps({"type": "message", "content": "thinking"})
                + "\n"
                + json.dumps({"type": "result", "result": '{"answer":"ok"}'})
                + "\n"
            ),
            stderr="",
        )

        result = llm_provider.KimiCLIProvider(model="kimi-model").correct(
            "prompt", None, SCHEMA
        )

        self.assertEqual({"answer": "ok"}, result)
        command = run.call_args.args[0]
        self.assertEqual("kimi", command[0])
        self.assertIn("stream-json", command)
        self.assertIn("kimi-model", command)

    @mock.patch("llm_provider.subprocess.run")
    def test_rejects_invalid_structure(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='{"result":"{}"}\n', stderr=""
        )

        with self.assertRaises(llm_provider.ProviderError):
            llm_provider.KimiCLIProvider().correct("prompt", None, SCHEMA)

    def test_local_validation_rejects_extra_root_and_item_fields(self):
        strict = {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                        "required": ["text"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["items"],
            "additionalProperties": False,
        }
        with self.assertRaises(llm_provider.ProviderError):
            llm_provider.validate_json_schema({"items": [], "extra": True}, strict)
        with self.assertRaises(llm_provider.ProviderError):
            llm_provider.validate_json_schema(
                {"items": [{"text": "ok", "extra": True}]}, strict
            )


class OpenAIProviderTests(unittest.TestCase):
    def test_uses_responses_api_and_custom_base_url(self):
        response_create = mock.Mock(return_value=types.SimpleNamespace(output_text='{"answer":"ok"}'))
        client = types.SimpleNamespace(
            responses=types.SimpleNamespace(create=response_create)
        )
        constructor = mock.Mock(return_value=client)
        fake_module = types.SimpleNamespace(OpenAI=constructor)
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "frame.png"
            image.write_bytes(b"png")
            with mock.patch.dict(
                os.environ,
                {
                    "OPENAI_API_KEY": "test-key",
                    "OPENAI_BASE_URL": "https://proxy.example/v1",
                },
                clear=True,
            ), mock.patch.dict(sys.modules, {"openai": fake_module}):
                provider = llm_provider.OpenAIProvider("test-model")
                result = provider.correct("prompt", image, SCHEMA)

        self.assertEqual({"answer": "ok"}, result)
        constructor.assert_called_once_with(
            api_key="test-key", timeout=300, base_url="https://proxy.example/v1"
        )
        kwargs = response_create.call_args.kwargs
        self.assertEqual("test-model", kwargs["model"])
        self.assertEqual("json_schema", kwargs["text"]["format"]["type"])
        self.assertTrue(kwargs["input"][0]["content"][1]["image_url"].startswith("data:image/png;base64,"))

    def test_requires_correctly_spelled_key(self):
        with mock.patch.dict(os.environ, {"OPNEAI_API_KEY": "typo"}, clear=True):
            with self.assertRaisesRegex(llm_provider.ProviderError, "OPNEAI_API_KEY is a typo"):
                llm_provider.OpenAIProvider("test-model", Path("missing.env"))


if __name__ == "__main__":
    unittest.main()

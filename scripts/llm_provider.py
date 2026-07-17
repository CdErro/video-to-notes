#!/usr/bin/env python3
"""Configurable LLM providers for subtitle correction."""

from __future__ import annotations

import base64
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Protocol


class ProviderError(RuntimeError):
    """Raised when a provider cannot return valid structured output."""


class Provider(Protocol):
    name: str
    model: str

    def correct(self, prompt: str, image: Path | None, schema: dict) -> dict: ...


def load_dotenv(path: Path) -> None:
    """Load the two supported OpenAI settings without overriding the process."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in {"OPENAI_API_KEY", "OPENAI_BASE_URL"} or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ[key] = value


def _matches_type(value: Any, expected: str) -> bool:
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }.get(expected, True)


def validate_json_schema(value: Any, schema: dict, path: str = "$") -> None:
    expected = schema.get("type")
    if expected and not _matches_type(value, expected):
        raise ProviderError(f"{path} must be {expected}")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                raise ProviderError(f"{path}.{key} is required")
        properties = schema.get("properties", {})
        for key, child in value.items():
            if key in properties:
                validate_json_schema(child, properties[key], f"{path}.{key}")
    if isinstance(value, list) and "items" in schema:
        for index, child in enumerate(value):
            validate_json_schema(child, schema["items"], f"{path}[{index}]")


def _parse_json_object(text: str, schema: dict) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(value, dict):
        return None
    validate_json_schema(value, schema)
    return value


def _json_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _json_strings(item)
    elif isinstance(value, dict):
        yield json.dumps(value, ensure_ascii=False)
        for key in ("structured_output", "output", "result", "content", "text", "message"):
            if key in value:
                yield from _json_strings(value[key])


class KimiCLIProvider:
    name = "kimi-cli"

    def __init__(self, model: str = "", timeout: int = 300):
        self.model = model
        self.timeout = timeout

    def correct(self, prompt: str, image: Path | None, schema: dict) -> dict:
        if image:
            prompt += f"\n\n参考画面（请读取此本地文件）：{image.resolve()}"
        command = ["kimi", "-p", prompt]
        if self.model:
            command.extend(["-m", self.model])
        command.extend(["--output-format", "stream-json"])
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=self.timeout, check=False
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as error:
            raise ProviderError(f"Kimi CLI unavailable or timed out: {error}") from error
        if result.returncode != 0:
            raise ProviderError(f"Kimi CLI failed ({result.returncode}): {result.stderr[:300]}")
        candidates: list[str] = []
        for line in result.stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            candidates.extend(_json_strings(event))
        for candidate in reversed(candidates):
            parsed = _parse_json_object(candidate, schema)
            if parsed is not None:
                return parsed
        raise ProviderError("Kimi CLI returned no valid final JSON object")


class OpenAIProvider:
    name = "openai"

    def __init__(self, model: str, env_file: Path = Path(".env"), timeout: int = 300):
        load_dotenv(env_file)
        key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not key:
            raise ProviderError("OPENAI_API_KEY is required (OPNEAI_API_KEY is a typo)")
        try:
            from openai import OpenAI
        except ImportError as error:
            raise ProviderError("openai package is not installed") from error
        kwargs: dict[str, Any] = {"api_key": key, "timeout": timeout}
        base_url = os.environ.get("OPENAI_BASE_URL", "").strip()
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)
        self.model = model

    def correct(self, prompt: str, image: Path | None, schema: dict) -> dict:
        content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt}]
        if image:
            mime = "image/png" if image.suffix.lower() == ".png" else "image/jpeg"
            encoded = base64.b64encode(image.read_bytes()).decode("ascii")
            content.append(
                {"type": "input_image", "image_url": f"data:{mime};base64,{encoded}"}
            )
        try:
            response = self.client.responses.create(
                model=self.model,
                input=[{"role": "user", "content": content}],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "subtitle_corrections",
                        "schema": schema,
                        "strict": True,
                    }
                },
            )
        except Exception as error:
            raise ProviderError(f"OpenAI request failed: {error}") from error
        parsed = _parse_json_object(response.output_text, schema)
        if parsed is None:
            raise ProviderError("OpenAI returned invalid structured output")
        return parsed


def create_provider(name: str, model: str, env_file: Path) -> Provider:
    if name == "kimi-cli":
        return KimiCLIProvider(model=model)
    if name == "openai":
        return OpenAIProvider(model=model, env_file=env_file)
    raise ProviderError(f"Unsupported provider: {name}")

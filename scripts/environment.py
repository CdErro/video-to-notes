#!/usr/bin/env python3
"""Detect and optionally install video-to-notes dependencies."""

from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 is rejected first
    tomllib = None


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / ".video-to-notes.toml"
REQUIREMENTS_PATH = ROOT / "requirements.txt"
MINIMUM_PYTHON = (3, 11)


@dataclass(frozen=True)
class CheckResult:
    name: str
    kind: str
    status: str
    required: bool
    detail: str
    path: str | None = None


PYTHON_PACKAGES = {
    "openai": ("openai", "openai", (2, 44, 0)),
    "yt-dlp": ("yt_dlp", "yt-dlp", (2026, 6, 9)),
    "Faster Whisper": ("faster_whisper", "faster-whisper", (1, 2, 1)),
    "Pillow": ("PIL", "Pillow", None),
}

COMMAND_MINIMUMS = {
    "FFmpeg": (4, 0),
    "FFprobe": (4, 0),
    "Kimi Code CLI": (0, 26, 0),
}

COMMANDS = {
    "FFmpeg": ("ffmpeg", "-version"),
    "FFprobe": ("ffprobe", "-version"),
    "yt-dlp CLI": ("yt-dlp", "--version"),
    "Pandoc": ("pandoc", "--version"),
    "XeLaTeX": ("xelatex", "--version"),
    "ImageMagick": ("magick", "-version"),
    "Kimi Code CLI": ("kimi", "--version"),
}

WINDOWS_PACKAGES = {
    "FFmpeg": ["winget", "install", "--id", "Gyan.FFmpeg", "-e", "--silent"],
    "ImageMagick": ["winget", "install", "--id", "ImageMagick.ImageMagick", "-e", "--silent"],
    "Pandoc": ["winget", "install", "--id", "JohnMacFarlane.Pandoc", "-e", "--silent"],
    "XeLaTeX": ["winget", "install", "--id", "MiKTeX.MiKTeX", "-e", "--silent"],
}

MACOS_PACKAGES = {
    "FFmpeg": ["brew", "install", "ffmpeg"],
    "ImageMagick": ["brew", "install", "imagemagick"],
    "Pandoc": ["brew", "install", "pandoc"],
    "XeLaTeX": ["brew", "install", "--cask", "mactex-no-gui"],
}

LINUX_PACKAGES = {
    "FFmpeg": ["sudo", "apt", "install", "-y", "ffmpeg"],
    "ImageMagick": ["sudo", "apt", "install", "-y", "imagemagick"],
    "Pandoc": ["sudo", "apt", "install", "-y", "pandoc"],
    "XeLaTeX": ["sudo", "apt", "install", "-y", "texlive-xetex", "texlive-lang-chinese"],
}

MANUAL_INSTALL_GUIDANCE = {
    "FFmpeg": "Install FFmpeg and ffprobe from https://ffmpeg.org/download.html",
    "ImageMagick": "Install ImageMagick from https://imagemagick.org/script/download.php",
    "Pandoc": "Install Pandoc from https://pandoc.org/installing.html",
    "XeLaTeX": "Install a TeX distribution that includes XeLaTeX and Chinese fonts.",
}


def _version_tuple(value: str) -> tuple[int, ...]:
    match = __import__("re").search(r"\d+(?:\.\d+)+", value)
    return tuple(int(part) for part in match.group().split(".")) if match else ()


def load_tool_overrides(path: Path = CONFIG_PATH) -> dict[str, str]:
    if not path.exists() or tomllib is None:
        return {}
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    tools = payload.get("tools", {})
    return {str(key): str(value) for key, value in tools.items() if value}


def required_names(
    output_format: str, provider: str, with_transcription: bool = False
) -> set[str]:
    required = {"Python", "yt-dlp", "Pillow", "FFmpeg", "FFprobe", "yt-dlp CLI"}
    if output_format in {"latex", "pdf", "all"}:
        required.add("Pandoc")
    if output_format in {"pdf", "all"}:
        required.add("XeLaTeX")
    if provider == "kimi-cli":
        required.add("Kimi Code CLI")
    if provider == "openai":
        required.update({"openai", "OPENAI_API_KEY"})
    if with_transcription:
        required.update({"Faster Whisper", "Whisper model"})
    return required


def check_python(required: set[str]) -> list[CheckResult]:
    version = platform.python_version()
    ready = sys.version_info >= MINIMUM_PYTHON
    results = [
        CheckResult(
            "Python",
            "runtime",
            "ready" if ready else "version_unsupported",
            True,
            version,
            sys.executable,
        )
    ]
    for display_name, (import_name, distribution, minimum) in PYTHON_PACKAGES.items():
        found = importlib.util.find_spec(import_name) is not None
        is_required = display_name in required
        detail = f"import {import_name}"
        status = "ready" if found else ("required_missing" if is_required else "optional_missing")
        if found:
            try:
                version = importlib.metadata.version(distribution)
                detail = version
                if minimum and _version_tuple(version) < minimum:
                    status = "version_unsupported"
            except importlib.metadata.PackageNotFoundError:
                pass
        results.append(
            CheckResult(
                display_name,
                "python_package",
                status,
                is_required,
                detail,
            )
        )
    return results


def command_path(command: str, overrides: dict[str, str]) -> str | None:
    configured = overrides.get(command)
    if configured:
        return configured
    return shutil.which(command)


def check_commands(required: set[str], overrides: dict[str, str]) -> list[CheckResult]:
    results = []
    for display_name, (command, version_arg) in COMMANDS.items():
        path = command_path(command, overrides)
        is_required = display_name in required
        if not path:
            status = "required_missing" if is_required else "optional_missing"
            results.append(CheckResult(display_name, "command", status, is_required, "not found"))
            continue
        try:
            completed = subprocess.run(
                [path, version_arg],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            output = (completed.stdout or completed.stderr).splitlines()
            detail = output[0].strip() if output else f"exit {completed.returncode}"
            status = "ready" if completed.returncode == 0 else "found_unusable"
            minimum = COMMAND_MINIMUMS.get(display_name)
            if status == "ready" and minimum and _version_tuple(detail) < minimum:
                status = "version_unsupported"
        except (OSError, subprocess.SubprocessError) as error:
            status = "found_unusable"
            detail = str(error)
        results.append(CheckResult(display_name, "command", status, is_required, detail, path))
    return results


def check_credentials(required: set[str]) -> list[CheckResult]:
    present = bool(os.environ.get("OPENAI_API_KEY", "").strip())
    is_required = "OPENAI_API_KEY" in required
    status = "ready" if present else ("required_missing" if is_required else "optional_missing")
    return [CheckResult("OPENAI_API_KEY", "credential", status, is_required, "set" if present else "not set")]


def whisper_settings(path: Path = CONFIG_PATH) -> dict:
    from transcribe import TranscriptionError, load_config

    try:
        config = load_config(path if path.exists() else None)
    except (OSError, ValueError, TranscriptionError) as error:
        raise ValueError(str(error)) from error
    return {"model": config.model, "cache_dir": config.cache_dir}


def check_whisper_model(required: bool, model: str, cache_dir: str | None) -> CheckResult:
    try:
        root = Path(cache_dir) if cache_dir else Path.home() / ".cache" / "huggingface" / "hub"
    except TypeError:
        return CheckResult(
            "Whisper model", "model", "found_unusable", required, "cache_dir must be a path"
        )
    repository = root / f"models--Systran--faster-whisper-{model}" / "snapshots"
    required_files = {"model.bin", "config.json", "tokenizer.json"}
    found = any(
        required_files <= {item.name for item in snapshot.iterdir() if item.is_file()}
        for snapshot in repository.iterdir()
    ) if repository.is_dir() else False
    return CheckResult(
        "Whisper model",
        "model",
        "ready" if found else ("required_missing" if required else "optional_missing"),
        required,
        f"{model} ({'cached' if found else 'not cached'})",
        str(repository) if found else None,
    )


def doctor(
    output_format: str,
    provider: str,
    config_path: Path = CONFIG_PATH,
    with_transcription: bool = False,
    whisper_model: str | None = None,
) -> list[CheckResult]:
    required = required_names(output_format, provider, with_transcription)
    overrides = load_tool_overrides(config_path)
    settings = whisper_settings(config_path)
    model = whisper_model or settings["model"]
    return (
        check_python(required)
        + check_commands(required, overrides)
        + check_credentials(required)
        + [check_whisper_model("Whisper model" in required, model, settings["cache_dir"])]
    )


def print_report(results: list[CheckResult], as_json: bool) -> None:
    if as_json:
        print(json.dumps({"checks": [asdict(item) for item in results]}, ensure_ascii=False, indent=2))
        return
    for item in results:
        marker = "required" if item.required else "optional"
        location = f" [{item.path}]" if item.path else ""
        print(f"{item.status:20} {item.name:18} ({marker}) {item.detail}{location}")


def target_python(target: str) -> tuple[list[str], list[list[str]]]:
    setup_commands: list[list[str]] = []
    if target.startswith("conda:"):
        environment = target.split(":", 1)[1]
        if not environment:
            raise ValueError("Conda target requires an environment name")
        listed = subprocess.run(
            ["conda", "env", "list", "--json"], capture_output=True, text=True, check=False
        )
        environments = json.loads(listed.stdout or "{}").get("envs", []) if listed.returncode == 0 else []
        if not any(Path(path).name.casefold() == environment.casefold() for path in environments):
            setup_commands.append(["conda", "create", "-n", environment, "python=3.11", "pip", "-y"])
        return ["conda", "run", "-n", environment, "python"], setup_commands
    if target.startswith("venv:"):
        directory = Path(target.split(":", 1)[1] or ".venv")
        python_path = directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if not python_path.exists():
            setup_commands.append([sys.executable, "-m", "venv", str(directory)])
        return [str(python_path)], setup_commands
    raise ValueError("Target must use conda:<name> or venv:<path>")


def target_requirements_ready(python_command: list[str]) -> bool:
    # Conda on Windows can corrupt multiline `python -c` arguments, so keep this script one line.
    script = (
        "import importlib.metadata as m,re,sys;"
        "v=lambda s:tuple(map(int,re.search(r'\\d+(?:\\.\\d+)+',s).group().split('.')));"
        "r=[('openai',(2,44,0),1),('faster-whisper',(1,2,1),1),"
        "('Pillow',(),0),('PyYAML',(6,0,3),1),('yt-dlp',(2026,6,9),0)];"
        "x=[(v(m.version(n)),q,e) for n,q,e in r];"
        "sys.exit(0 if all((a==q) if e else ((not q) or a>=q) for a,q,e in x) else 1)"
    )
    try:
        completed = subprocess.run(
            python_command + ["-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return completed.returncode == 0


def installation_commands(
    results: list[CheckResult],
    target: str,
    whisper_model: str = "small",
    whisper_cache_dir: str | None = None,
) -> list[list[str]]:
    python_command, commands = target_python(target)
    if commands or not target_requirements_ready(python_command):
        commands.append(python_command + ["-m", "pip", "install", "-r", str(REQUIREMENTS_PATH)])
    if any(item.name == "Whisper model" and item.required and item.status != "ready" for item in results):
        command = python_command + [
            str(ROOT / "scripts" / "transcribe.py"), "download-model", "--model", whisper_model
        ]
        if whisper_cache_dir:
            command.extend(["--cache-dir", whisper_cache_dir])
        commands.append(command)
    package_map = WINDOWS_PACKAGES if os.name == "nt" else MACOS_PACKAGES if sys.platform == "darwin" else LINUX_PACKAGES
    manager = "winget" if os.name == "nt" else "brew" if sys.platform == "darwin" else "apt"
    manager_available = shutil.which(manager) is not None
    for item in results:
        if (
            manager_available
            and item.kind == "command"
            and item.required
            and item.status != "ready"
            and item.name in package_map
        ):
            commands.append(package_map[item.name])
    return commands


def manual_install_guidance(results: list[CheckResult]) -> list[str]:
    manager = "winget" if os.name == "nt" else "brew" if sys.platform == "darwin" else "apt"
    if shutil.which(manager):
        return []
    return [
        MANUAL_INSTALL_GUIDANCE[item.name]
        for item in results
        if item.kind == "command"
        and item.required
        and item.status != "ready"
        and item.name in MANUAL_INSTALL_GUIDANCE
    ]


def run_install(commands: list[list[str]], assume_yes: bool) -> int:
    if not commands:
        print("Environment already satisfies the selected profile.")
        return 0
    print("Planned commands:")
    for command in commands:
        print("  " + subprocess.list2cmdline(command))
    if not assume_yes and input("Run these commands? [y/N] ").strip().casefold() != "y":
        print("Installation cancelled.")
        return 1
    for command in commands:
        completed = subprocess.run(command, check=False)
        if completed.returncode != 0:
            print(f"Command failed ({completed.returncode}): {subprocess.list2cmdline(command)}", file=sys.stderr)
            return completed.returncode
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    for action in ("doctor", "install"):
        sub = subparsers.add_parser(action)
        sub.add_argument("--format", choices=("markdown", "latex", "pdf", "all"), default="markdown")
        sub.add_argument("--provider", choices=("kimi-cli", "openai", "none"), default="kimi-cli")
        sub.add_argument("--config", type=Path, default=CONFIG_PATH)
        sub.add_argument("--with-transcription", action="store_true")
        sub.add_argument("--whisper-model")
        if action == "doctor":
            sub.add_argument("--json", action="store_true")
        else:
            sub.add_argument("--yes", action="store_true")
            sub.add_argument("--target", default="conda:video-to-notes" if shutil.which("conda") else "venv:.venv")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        settings = whisper_settings(args.config)
        whisper_model = args.whisper_model or settings["model"]
        results = doctor(
            args.format,
            args.provider,
            args.config,
            args.with_transcription,
            whisper_model,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Cannot read configuration: {error}", file=sys.stderr)
        return 2
    if args.action == "doctor":
        print_report(results, args.json)
        return int(any(item.required and item.status != "ready" for item in results))
    try:
        commands = installation_commands(
            results, args.target, whisper_model, settings["cache_dir"]
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Cannot prepare installation: {error}", file=sys.stderr)
        return 2
    guidance = manual_install_guidance(results)
    if guidance:
        print("No supported system package manager was found. Install manually:")
        for item in guidance:
            print(f"  - {item}")
        if not commands:
            return 1
    result = run_install(commands, args.yes)
    return 1 if result == 0 and guidance else result


if __name__ == "__main__":
    raise SystemExit(main())

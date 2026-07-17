#!/usr/bin/env python3
"""Transcribe media to SRT with hardware-aware faster-whisper defaults."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None

from glossary import DEFAULT_USER_ROOT, build_prompt, detect_domains


class TranscriptionError(RuntimeError):
    """Raised when faster-whisper cannot produce a valid transcript."""


@dataclass(frozen=True)
class TranscriptionConfig:
    model: str = "small"
    device: str = "cpu"
    compute_type: str = "int8"
    cpu_threads: int = 8
    language: str | None = None
    vad_filter: bool = True
    cache_dir: str | None = None


def default_config() -> TranscriptionConfig:
    return TranscriptionConfig(cpu_threads=max(1, min(8, os.cpu_count() or 1)))


def validate_config(config: TranscriptionConfig) -> TranscriptionConfig:
    if not isinstance(config.model, str) or config.model not in {"tiny", "base", "small", "medium"}:
        raise TranscriptionError("Whisper model must be tiny, base, small, or medium")
    if not isinstance(config.device, str) or config.device not in {"cpu", "cuda"}:
        raise TranscriptionError("Whisper device must be cpu or cuda")
    valid_compute_types = {"int8", "int8_float16", "float16", "float32"}
    if not isinstance(config.compute_type, str) or config.compute_type not in valid_compute_types:
        raise TranscriptionError(
            "Whisper compute_type must be int8, int8_float16, float16, or float32"
        )
    if not isinstance(config.cpu_threads, int) or isinstance(config.cpu_threads, bool) or config.cpu_threads < 1:
        raise TranscriptionError("Whisper cpu_threads must be a positive integer")
    if config.language is not None and (
        not isinstance(config.language, str) or not config.language.strip()
    ):
        raise TranscriptionError("Whisper language must be a non-empty string or omitted")
    if not isinstance(config.vad_filter, bool):
        raise TranscriptionError("Whisper vad_filter must be true or false")
    if config.cache_dir is not None and not isinstance(config.cache_dir, str):
        raise TranscriptionError("Whisper cache_dir must be a path string or omitted")
    return config


def load_config(path: Path | None) -> TranscriptionConfig:
    defaults = asdict(default_config())
    if path and path.is_file():
        if tomllib is None:
            raise TranscriptionError("Python 3.11+ is required to read TOML configuration")
        try:
            payload = tomllib.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError) as error:
            raise TranscriptionError(f"Cannot read Whisper configuration: {error}") from error
        section = payload.get("whisper", {})
        if not isinstance(section, dict):
            raise TranscriptionError("[whisper] configuration must be a table")
        defaults.update({key: value for key, value in section.items() if key in defaults})
    return validate_config(TranscriptionConfig(**defaults))


def format_srt_time(seconds: float) -> str:
    milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", delete=False, dir=path.parent, suffix=".tmp"
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    try:
        temporary.replace(path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def transcribe_media(
    media: Path,
    output: Path,
    config: TranscriptionConfig,
    initial_prompt: str = "",
) -> dict:
    if not media.is_file():
        raise TranscriptionError(f"Media file does not exist: {media}")
    try:
        from faster_whisper import WhisperModel
    except ImportError as error:
        raise TranscriptionError(
            "faster-whisper is not installed; run setup with transcription enabled"
        ) from error
    try:
        model = WhisperModel(
            config.model,
            device=config.device,
            compute_type=config.compute_type,
            cpu_threads=config.cpu_threads,
            download_root=config.cache_dir,
        )
        segments, info = model.transcribe(
            str(media),
            language=config.language,
            initial_prompt=initial_prompt or None,
            vad_filter=config.vad_filter,
            beam_size=5,
        )
        completed = list(segments)
    except Exception as error:
        raise TranscriptionError(f"Whisper transcription failed: {error}") from error
    if not completed:
        raise TranscriptionError("Whisper returned no speech segments")
    blocks = []
    for segment in completed:
        text = str(segment.text).strip()
        if not text:
            continue
        index = len(blocks) + 1
        blocks.append(
            f"{index}\n{format_srt_time(float(segment.start))} --> "
            f"{format_srt_time(float(segment.end))}\n{text}"
        )
    if not blocks:
        raise TranscriptionError("Whisper returned only empty speech segments")
    atomic_write_text(output, "\n\n".join(blocks) + "\n")
    metadata = {
        "engine": "faster-whisper",
        "model": config.model,
        "device": config.device,
        "compute_type": config.compute_type,
        "cpu_threads": config.cpu_threads,
        "vad_filter": config.vad_filter,
        "language": getattr(info, "language", config.language),
        "language_probability": getattr(info, "language_probability", None),
        "segments": len(blocks),
        "output": str(output.resolve()),
    }
    atomic_write_text(
        output.with_name("transcription.json"),
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
    )
    return metadata


def download_model(model: str, cache_dir: str | None = None) -> str:
    try:
        from faster_whisper.utils import download_model as fetch_model
    except ImportError as error:
        raise TranscriptionError("faster-whisper is not installed") from error
    try:
        return str(fetch_model(model, cache_dir=cache_dir))
    except Exception as error:
        raise TranscriptionError(f"Whisper model download failed: {error}") from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("media", type=Path)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--config", type=Path, default=Path(".video-to-notes.toml"))
    run.add_argument("--model")
    run.add_argument("--device", choices=("cpu", "cuda"))
    run.add_argument("--compute-type")
    run.add_argument("--cpu-threads", type=int)
    run.add_argument("--language")
    run.add_argument("--context", default="通用视频")
    run.add_argument("--domain")
    run.add_argument("--glossary-root", type=Path, default=DEFAULT_USER_ROOT)
    fetch = subparsers.add_parser("download-model")
    fetch.add_argument("--model", default="small")
    fetch.add_argument("--cache-dir")
    args = parser.parse_args()
    try:
        if args.command == "download-model":
            print(download_model(args.model, args.cache_dir))
            return 0
        config = load_config(args.config)
        overrides = {
            "model": args.model,
            "device": args.device,
            "compute_type": args.compute_type,
            "cpu_threads": args.cpu_threads,
            "language": args.language,
        }
        values = asdict(config)
        values.update({key: value for key, value in overrides.items() if value is not None})
        config = validate_config(TranscriptionConfig(**values))
        domains = ["general", args.domain] if args.domain and args.domain != "general" else detect_domains(args.context)
        prompt = build_prompt(args.context, domains, args.glossary_root)
        print(json.dumps(transcribe_media(args.media, args.output, config, prompt), ensure_ascii=False, indent=2))
        return 0
    except (TranscriptionError, OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    raise SystemExit(main())

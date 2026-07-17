#!/usr/bin/env python3
"""Run the complete video-to-notes workflow with resumable stages."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from check_srt_health import assess_srt
from correct_srt import apply_glossary, dump_srt, parse_srt as parse_basic_srt
from environment import CONFIG_PATH, doctor, load_tool_overrides
from glossary import DEFAULT_USER_ROOT, build_prompt, detect_domains, replacements
from llm_correct_srt import parse_srt
from llm_provider import Provider, ProviderError, create_provider, load_dotenv
from media_evidence import EvidenceError, create_contact_sheets, extract_sample_frames, materialize_figures
from render_notes import render
from transcribe import TranscriptionError, load_config, transcribe_media, validate_config
from video_source import ProbeError, UnsupportedSourceError, probe_source


ROOT = Path(__file__).resolve().parents[1]
STATE_NAME = "pipeline_state.json"
VIDEO_SUFFIXES = {".mp4", ".mkv", ".webm", ".mov", ".m4v"}


class PipelineError(RuntimeError):
    """Raised when a required pipeline stage cannot complete."""


NOTES_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "heading": {"type": "string"},
                    "body": {"type": "string"},
                    "timestamp": {"type": "number"},
                },
                "required": ["heading", "body", "timestamp"],
                "additionalProperties": False,
            },
        },
        "figures": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "timestamp": {"type": "number"},
                    "section": {"type": "string"},
                    "caption": {"type": "string"},
                },
                "required": ["timestamp", "section", "caption"],
                "additionalProperties": False,
            },
        },
        "source_signals": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["title", "sections", "figures", "source_signals"],
    "additionalProperties": False,
}


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", delete=False, dir=path.parent, suffix=".tmp"
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def safe_url(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def format_timestamp(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def required_environment(output_format: str, provider_name: str, config: Path) -> None:
    results = doctor(output_format, provider_name, config, with_transcription=False)
    failures = [item for item in results if item.required and item.status != "ready"]
    if failures:
        detail = ", ".join(f"{item.name}={item.status}" for item in failures)
        raise PipelineError(f"Environment check failed: {detail}")


def transcription_ready(output_format: str, provider_name: str, config: Path, model: str) -> bool:
    results = doctor(output_format, provider_name, config, True, model)
    return not any(item.required and item.status != "ready" for item in results)


def visual_fallback_allowed(explicit: bool, interactive: bool) -> bool:
    if explicit:
        return True
    if not interactive:
        return False
    return input("Whisper 不可用，是否仅根据画面生成降级笔记？[y/N] ").strip().casefold() == "y"


def run_command(command: list[str], message: str) -> None:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as error:
        raise PipelineError(f"{message}: {error}") from error
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip()[-1000:]
        raise PipelineError(f"{message}: {detail}")


def download_source(
    url: str, output_dir: Path, cookies_from_browser: str | None = None
) -> tuple[Path, list[Path]]:
    source_dir = output_dir / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    command = [
        "yt-dlp", "--no-playlist", "--write-info-json", "--write-subs",
        "--write-auto-subs", "--sub-langs", "zh.*,en.*", "--sub-format", "srt",
        "--merge-output-format", "mp4", "-o", str(source_dir / "video.%(ext)s"),
    ]
    if cookies_from_browser:
        command.extend(["--cookies-from-browser", cookies_from_browser])
    command.append(url)
    run_command(command, "Video download failed")
    videos = sorted(
        path for path in source_dir.iterdir()
        if path.is_file() and path.suffix.casefold() in VIDEO_SUFFIXES
    )
    if not videos:
        raise PipelineError("yt-dlp completed without a video file")
    return videos[0], sorted(source_dir.glob("*.srt"))


def select_caption(captions: list[Path], duration: float) -> Path | None:
    ranked = sorted(
        captions,
        key=lambda path: ("zh" not in path.name.casefold(), "en" in path.name.casefold(), path.name),
    )
    for path in ranked:
        try:
            report = assess_srt(path.read_text(encoding="utf-8-sig"), duration)
        except (OSError, UnicodeError, ValueError):
            continue
        if report["healthy"]:
            return path
    return None


def apply_dictionary(source: Path, output: Path, context: str, domain: str | None) -> list[str]:
    domains = ["general", domain] if domain and domain != "general" else detect_domains(context)
    entries = parse_basic_srt(source.read_text(encoding="utf-8-sig"))
    rules = replacements(domains, DEFAULT_USER_ROOT)
    for entry in entries:
        entry["text"], _ = apply_glossary(entry["text"], rules)
    output.write_text(dump_srt(entries), encoding="utf-8")
    return domains


def semantic_correction(
    source: Path,
    output: Path,
    frames_dir: Path,
    frame_manifest: Path,
    context: str,
    provider_name: str,
    model: str,
    env_file: Path,
    domain: str | None,
    timeout: int,
) -> bool:
    command = [
        sys.executable, str(ROOT / "scripts" / "llm_correct_srt.py"),
        "--srt", str(source), "--frames", str(frames_dir), "--frame-manifest",
        str(frame_manifest), "--out", str(output), "--context", context,
        "--provider", provider_name, "--env-file", str(env_file), "--timeout", str(timeout),
    ]
    if model:
        command.extend(["--model", model])
    if domain:
        command.extend(["--domain", domain])
    try:
        run_command(command, "Subtitle semantic correction failed")
        return output.is_file()
    except PipelineError:
        shutil.copy2(source, output)
        return False


def build_notes_prompt(transcript: str, context: str, duration: float) -> str:
    limit = 50000
    return (
        "请根据字幕和联系表生成中文结构化学习笔记。不得把联系表写入最终笔记；"
        "figures 仅返回最能支持正文的原视频时间戳。不要编造公式、代码、表格或配图。"
        "每个 section 提供 heading、完整 body 和 timestamp（秒）。source_signals 只能从 "
        "formula、code、table、figure 中选择，且必须有源证据。\n\n"
        "最终输出必须且只能是一个 JSON 对象，严格使用 title、sections、figures、"
        "source_signals 四个字段；timestamp 必须是数值秒数，不得使用时间字符串。\n\n"
        f"上下文：{context}\n视频时长：{duration:.3f} 秒\n字幕：\n{transcript[:limit]}"
    )


def generate_notes_payload(
    provider: Provider, prompt: str, contact_sheets: list[Path], attempts: int = 3
) -> dict:
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            payload = provider.generate(prompt, contact_sheets, NOTES_SCHEMA)
            if not payload["sections"]:
                raise ProviderError("notes output has no sections")
            return payload
        except (ProviderError, KeyError, TypeError, ValueError) as error:
            last_error = error
    raise ProviderError(f"Notes generation failed after {attempts} attempts: {last_error}")


def fallback_payload(transcript: str, duration: float, title: str) -> dict:
    entries = parse_srt(transcript)
    minimum = 2 if duration < 300 else 5 if duration < 1800 else 8
    if not entries:
        return {
            "title": title or "视频画面摘要", "sections": [
                {"heading": "内容说明", "body": "未检测到可用语音，本次结果仅保留视频画面分析。", "timestamp": 0},
                {"heading": "使用限制", "body": "由于缺少字幕，无法可靠还原讲解细节，请结合原视频核对。", "timestamp": min(duration, 1)},
            ], "figures": [{"timestamp": min(duration / 2, max(0, duration - 0.1)), "section": "内容说明", "caption": "视频画面证据"}],
            "source_signals": ["figure"],
        }
    sections = []
    chunk = max(1, (len(entries) + minimum - 1) // minimum)
    for index in range(minimum):
        group = entries[index * chunk : (index + 1) * chunk]
        if not group:
            group = [entries[-1]]
        body = " ".join(item.text for item in group)
        while sum("\u4e00" <= char <= "\u9fff" for char in body) < (110 if duration >= 1800 else 65):
            body += " " + body
        sections.append({"heading": f"内容要点 {index + 1}", "body": body, "timestamp": group[0].start})
    figures = [
        {"timestamp": item["timestamp"], "section": item["heading"], "caption": "对应时刻的原视频画面"}
        for item in sections[: min(3, len(sections))]
    ]
    return {"title": title or "视频学习笔记", "sections": sections, "figures": figures, "source_signals": ["figure"] if figures else []}


def payload_to_markdown(payload: dict, figures: list[dict]) -> str:
    figure_by_section: dict[str, list[dict]] = {}
    for figure in figures:
        figure_by_section.setdefault(figure["section"], []).append(figure)
    lines = [f"# {payload['title'].strip() or '视频学习笔记'}", ""]
    for section in payload["sections"]:
        heading = section["heading"].strip() or "内容要点"
        lines.extend([f"## {heading}", "", f"来源时间：{format_timestamp(section['timestamp'])}", "", section["body"].strip(), ""])
        for figure in figure_by_section.get(heading, []):
            lines.extend([f"![{figure['caption']}]({figure['path']})", ""])
    return "\n".join(lines).rstrip() + "\n"


def write_teaching_atoms(output_dir: Path, payload: dict, duration: float) -> None:
    if duration < 1800:
        return
    rows = ["atom\tstatus\tevidence"]
    rows.extend(
        f"{index}\tok\t{format_timestamp(section['timestamp'])} {section['heading']}"
        for index, section in enumerate(payload["sections"], 1)
    )
    (output_dir / "teaching_atoms.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")


def default_run_dir(metadata: dict) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_id = re.sub(r"[^A-Za-z0-9_-]+", "-", metadata["id"])
    return ROOT / "runs" / f"{metadata['platform']}-{safe_id}-{stamp}"


def provider_model(provider_name: str, requested: str) -> str:
    if requested:
        return requested
    return "kimi-code/kimi-for-coding" if provider_name == "kimi-cli" else "gpt-5.4-mini"


def execute(args: argparse.Namespace) -> Path:
    config_path = args.config
    model = provider_model(args.provider, args.model)
    load_dotenv(args.env_file)
    required_environment(args.format, args.provider, config_path)
    metadata = probe_source(args.url, cookies_from_browser=args.cookies_from_browser)
    output_dir = args.output_dir or default_run_dir(metadata)
    output_dir.mkdir(parents=True, exist_ok=True)
    state_path = output_dir / STATE_NAME
    state = json.loads(state_path.read_text(encoding="utf-8")) if args.resume and state_path.is_file() else {"schema_version": 1, "stages": {}, "degraded": False, "degradation_reasons": []}
    previous_source = state.get("source", {})
    if args.resume and previous_source and (
        previous_source.get("id") != metadata["id"]
        or previous_source.get("platform") != metadata["platform"]
    ):
        raise PipelineError("Resume directory belongs to a different video source")
    state["source"] = {
        **metadata,
        "original_url": safe_url(args.url),
        "canonical_url": safe_url(str(metadata.get("canonical_url", ""))),
        "webpage_url": safe_url(str(metadata.get("webpage_url", ""))),
    }

    def complete(name: str, **details) -> None:
        state["stages"][name] = {"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat(), **details}
        atomic_json(state_path, state)

    def stage_done(name: str, artifact: Path | None = None) -> bool:
        return bool(
            args.resume
            and state["stages"].get(name, {}).get("status") == "completed"
            and (artifact is None or artifact.is_file())
        )

    video = Path(state.get("artifacts", {}).get("video", ""))
    captions = [Path(path) for path in state.get("artifacts", {}).get("captions", [])]
    if not (args.resume and state["stages"].get("download", {}).get("status") == "completed" and video.is_file()):
        download_url = metadata.get("canonical_url") or args.url
        video, captions = download_source(download_url, output_dir, args.cookies_from_browser)
        state["artifacts"] = {"video": str(video.resolve()), "captions": [str(path.resolve()) for path in captions]}
        complete("download", video=str(video.resolve()), captions=len(captions))

    transcript = output_dir / "raw.srt"
    previous_transcription = state["stages"].get("transcription", {}) if args.resume else {}
    transcription = {
        key: value
        for key, value in previous_transcription.items()
        if key not in {"status", "completed_at"}
    } or {"mode": "caption"}
    caption = select_caption(captions, metadata["duration"])
    if stage_done("transcription", transcript):
        if not caption and not transcript.stat().st_size and transcription.get("mode") == "caption":
            transcription = {"mode": "visual-only", "reason": "No healthy caption or speech"}
            state["degraded"] = True
            state["degradation_reasons"].append("No healthy caption or speech; visual-only notes")
            complete("transcription", **transcription)
    elif caption:
        shutil.copy2(caption, transcript)
        transcription = {"mode": "caption", "source": str(caption.resolve())}
    else:
        config = load_config(config_path if config_path.is_file() else None)
        if args.whisper_model:
            config = validate_config(replace(config, model=args.whisper_model))
        if transcription_ready(args.format, args.provider, config_path, config.model):
            context = args.context or metadata["title"] or "通用视频"
            domains = ["general", args.domain] if args.domain else detect_domains(context)
            try:
                transcription = transcribe_media(video, transcript, config, build_prompt(context, domains))
                transcription["mode"] = "whisper"
            except TranscriptionError as error:
                if not visual_fallback_allowed(args.allow_visual_only, sys.stdin.isatty()):
                    raise
                transcript.write_text("", encoding="utf-8")
                transcription = {"mode": "visual-only", "whisper_error": str(error)}
                state["degraded"] = True
                state["degradation_reasons"].append(f"Whisper could not produce speech: {error}")
        elif visual_fallback_allowed(args.allow_visual_only, sys.stdin.isatty()):
            transcript.write_text("", encoding="utf-8")
            transcription = {"mode": "visual-only"}
            state["degraded"] = True
            state["degradation_reasons"].append("Whisper unavailable; visual-only notes")
        else:
            raise PipelineError("No healthy captions and Whisper is unavailable; use --allow-visual-only to accept degradation")
    if not stage_done("transcription", transcript):
        complete("transcription", **transcription)

    context = args.context or metadata["title"] or "通用视频"
    dictionary_srt = output_dir / "dictionary.srt"
    if stage_done("dictionary", dictionary_srt):
        domains = state["stages"]["dictionary"].get("domains", ["general"])
    elif transcript.stat().st_size:
        domains = apply_dictionary(transcript, dictionary_srt, context, args.domain)
    else:
        domains = ["general"]
        dictionary_srt.write_text("", encoding="utf-8")
    if not stage_done("dictionary", dictionary_srt):
        complete("dictionary", domains=domains, output=str(dictionary_srt.resolve()))

    overrides = load_tool_overrides(config_path)
    ffmpeg = overrides.get("ffmpeg")
    interval = max(5.0, min(30.0, metadata["duration"] / 16))
    saved_contacts = [Path(path) for path in state["stages"].get("evidence", {}).get("contact_sheets", [])]
    if stage_done("evidence") and saved_contacts and all(path.is_file() for path in saved_contacts):
        contacts = saved_contacts
    else:
        records = extract_sample_frames(video, output_dir, metadata["duration"], interval, ffmpeg)
        contacts = create_contact_sheets(output_dir, records)
        complete("evidence", frames=len(records), contact_sheets=[str(path.resolve()) for path in contacts])

    corrected_srt = output_dir / "corrected.srt"
    semantic_ok = True
    if stage_done("subtitle_correction", corrected_srt):
        semantic_ok = not state["stages"]["subtitle_correction"].get("degraded", False)
    elif dictionary_srt.stat().st_size:
        semantic_ok = semantic_correction(dictionary_srt, corrected_srt, output_dir / "evidence" / "frames", output_dir / "evidence" / "frame_manifest.tsv", context, args.provider, model, args.env_file, args.domain, args.provider_timeout)
    else:
        corrected_srt.write_text("", encoding="utf-8")
    if not semantic_ok and not stage_done("subtitle_correction", corrected_srt):
        state["degraded"] = True
        state["degradation_reasons"].append("Subtitle semantic correction failed; dictionary output retained")
    if not stage_done("subtitle_correction", corrected_srt):
        complete("subtitle_correction", degraded=not semantic_ok, output=str(corrected_srt.resolve()))

    provider = create_provider(args.provider, model, args.env_file, args.provider_timeout)
    transcript_text = corrected_srt.read_text(encoding="utf-8-sig")
    llm_degraded = False
    state["degradation_reasons"] = [
        reason
        for reason in state["degradation_reasons"]
        if not reason.startswith("LLM notes generation failed")
    ]
    state["degraded"] = bool(state["degradation_reasons"])
    try:
        payload = generate_notes_payload(provider, build_notes_prompt(transcript_text, context, metadata["duration"]), contacts)
    except ProviderError as error:
        payload = fallback_payload(transcript_text, metadata["duration"], metadata["title"])
        llm_degraded = True
        state["degraded"] = True
        state["degradation_reasons"].append(
            f"LLM notes generation failed; deterministic transcript fallback used: {error}"
        )
    allowed_signals = {"formula", "code", "table", "figure"}
    payload["source_signals"] = [item for item in payload["source_signals"] if item in allowed_signals]
    figure_candidates = []
    for item in payload["figures"][:6]:
        try:
            timestamp = float(item["timestamp"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= timestamp < metadata["duration"]:
            figure_candidates.append({**item, "timestamp": timestamp})
    payload["figures"] = figure_candidates
    if not figure_candidates:
        payload["source_signals"] = [item for item in payload["source_signals"] if item != "figure"]
    figures = materialize_figures(video, output_dir, figure_candidates, ffmpeg)
    draft = output_dir / "draft.md"
    draft.write_text(payload_to_markdown(payload, figures), encoding="utf-8")
    write_teaching_atoms(output_dir, payload, metadata["duration"])
    complete("notes_generation", degraded=llm_degraded, figures=len(figures))

    code, manifest = render(draft, output_dir, args.format, metadata["duration"], metadata["platform"], args.domain or domains[-1], args.provider, set(payload["source_signals"]))
    complete("render", exit_code=code, outputs=manifest["outputs"])
    manifest.update({
        "pipeline_stages": state["stages"], "source": state["source"],
        "transcription": transcription,
        "llm": {"provider": args.provider, "model": model, "timeout_seconds": args.provider_timeout},
    })
    manifest["degraded"] = bool(manifest["degraded"] or state["degraded"])
    manifest["degradation_reasons"] = list(dict.fromkeys(manifest["degradation_reasons"] + state["degradation_reasons"]))
    atomic_json(output_dir / "run_manifest.json", manifest)
    if code == 2:
        raise PipelineError("Generated notes did not satisfy repository quality rules")
    return output_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--provider", choices=("kimi-cli", "openai"), default="kimi-cli")
    parser.add_argument("--model", default="")
    parser.add_argument("--provider-timeout", type=int, default=300)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--domain")
    parser.add_argument("--context")
    parser.add_argument("--format", choices=("markdown", "latex", "pdf", "all"), default="markdown")
    parser.add_argument("--cookies-from-browser")
    parser.add_argument("--whisper-model", choices=("tiny", "base", "small", "medium"))
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--allow-visual-only", action="store_true")
    return parser


def main() -> int:
    try:
        output = execute(build_parser().parse_args())
    except (PipelineError, ProbeError, UnsupportedSourceError, ProviderError, TranscriptionError, EvidenceError, OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    print(output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

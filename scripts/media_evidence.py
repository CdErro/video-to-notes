#!/usr/bin/env python3
"""Extract timestamped evidence frames and final note figures from a video."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


class EvidenceError(RuntimeError):
    """Raised when FFmpeg cannot produce a requested evidence image."""


def _run_ffmpeg(video: Path, timestamp: float, target: Path, ffmpeg: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-ss", f"{timestamp:.3f}",
        "-i", str(video), "-frames:v", "1", "-q:v", "2", "-y", str(target),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as error:
        raise EvidenceError(f"FFmpeg unavailable: {error}") from error
    if result.returncode != 0 or not target.is_file():
        detail = (result.stderr or result.stdout or "no output frame").strip()[-500:]
        raise EvidenceError(f"FFmpeg frame extraction failed at {timestamp:.3f}s: {detail}")


def extract_sample_frames(
    video: Path,
    output_dir: Path,
    duration: float,
    interval: float = 15.0,
    ffmpeg: str | None = None,
) -> list[dict]:
    if duration <= 0 or interval <= 0:
        raise ValueError("duration and interval must be positive")
    executable = ffmpeg or shutil.which("ffmpeg")
    if not executable:
        raise EvidenceError("FFmpeg executable was not found")
    frames_dir = output_dir / "evidence" / "frames"
    records: list[dict] = []
    timestamp = 0.0
    while timestamp < duration:
        name = f"frame_{len(records) + 1:04d}.jpg"
        _run_ffmpeg(video, timestamp, frames_dir / name, executable)
        records.append({"frame": name, "timestamp": round(timestamp, 3)})
        timestamp += interval
    manifest = output_dir / "evidence" / "frame_manifest.tsv"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        "frame\ttimestamp\n"
        + "".join(f"{item['frame']}\t{item['timestamp']:.3f}\n" for item in records),
        encoding="utf-8",
    )
    return records


def materialize_figures(
    video: Path,
    output_dir: Path,
    candidates: list[dict],
    ffmpeg: str | None = None,
) -> list[dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    executable = ffmpeg or shutil.which("ffmpeg")
    if not executable:
        raise EvidenceError("FFmpeg executable was not found")
    records: list[dict] = []
    seen: set[float] = set()
    for candidate in candidates:
        timestamp = round(float(candidate["timestamp"]), 3)
        if timestamp < 0 or timestamp in seen:
            continue
        seen.add(timestamp)
        target = output_dir / "figures" / f"figure_{len(records) + 1:03d}.jpg"
        _run_ffmpeg(video, timestamp, target, executable)
        records.append(
            {
                "path": target.relative_to(output_dir).as_posix(),
                "timestamp": timestamp,
                "section": str(candidate.get("section", "")),
                "caption": str(candidate.get("caption", "")),
            }
        )
    (output_dir / "figure_manifest.json").write_text(
        json.dumps({"figures": records}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    sample = subparsers.add_parser("sample")
    sample.add_argument("video", type=Path)
    sample.add_argument("--output-dir", type=Path, required=True)
    sample.add_argument("--duration", type=float, required=True)
    sample.add_argument("--interval", type=float, default=15.0)
    sample.add_argument("--ffmpeg")
    figure = subparsers.add_parser("figures")
    figure.add_argument("video", type=Path)
    figure.add_argument("--output-dir", type=Path, required=True)
    figure.add_argument("--candidates", type=Path, required=True)
    figure.add_argument("--ffmpeg")
    args = parser.parse_args()
    try:
        if args.command == "sample":
            records = extract_sample_frames(
                args.video, args.output_dir, args.duration, args.interval, args.ffmpeg
            )
        else:
            payload = json.loads(args.candidates.read_text(encoding="utf-8-sig"))
            records = materialize_figures(
                args.video, args.output_dir, payload["figures"], args.ffmpeg
            )
    except (EvidenceError, OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(records, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

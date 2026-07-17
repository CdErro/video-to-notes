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
    while timestamp < duration and duration - timestamp >= 0.1:
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


def create_contact_sheets(
    output_dir: Path, records: list[dict], tiles_per_sheet: int = 16
) -> list[Path]:
    if tiles_per_sheet < 1:
        raise ValueError("tiles_per_sheet must be positive")
    try:
        from PIL import Image, ImageDraw
    except ImportError as error:
        raise EvidenceError("Pillow is required to create contact sheets") from error
    frames_dir = output_dir / "evidence" / "frames"
    contact_dir = output_dir / "evidence" / "contact_sheets"
    contact_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    tile_width, tile_height, label_height = 320, 180, 24
    columns = 4
    for offset in range(0, len(records), tiles_per_sheet):
        group = records[offset : offset + tiles_per_sheet]
        rows = (len(group) + columns - 1) // columns
        canvas = Image.new("RGB", (columns * tile_width, rows * (tile_height + label_height)), "black")
        draw = ImageDraw.Draw(canvas)
        for position, record in enumerate(group):
            source = frames_dir / record["frame"]
            if not source.is_file():
                raise EvidenceError(f"Evidence frame is missing: {source}")
            with Image.open(source) as image:
                image = image.convert("RGB")
                image.thumbnail((tile_width, tile_height))
                x = (position % columns) * tile_width
                y = (position // columns) * (tile_height + label_height)
                canvas.paste(image, (x, y))
                draw.text((x + 4, y + tile_height + 4), f"{record['timestamp']:.1f}s", fill="white")
        target = contact_dir / f"contact_{len(created) + 1:03d}.jpg"
        canvas.save(target, quality=88)
        created.append(target)
    return created


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

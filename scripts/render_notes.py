#!/usr/bin/env python3
"""Validate Chinese Markdown notes and optionally render LaTeX/PDF outputs."""

from __future__ import annotations

import argparse
import json
import platform
import re
import shutil
import subprocess
import sys
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


FIGURE_PATH_PATTERN = re.compile(r"figures/figure_\d{3}\.jpg\Z")


@dataclass(frozen=True)
class QualityRule:
    name: str
    minimum_cjk: int
    minimum_sections: int
    minimum_timestamps: int
    require_atom_audit: bool


def quality_rule(duration_seconds: float) -> QualityRule:
    if duration_seconds < 0:
        raise ValueError("duration_seconds must be non-negative")
    if duration_seconds < 300:
        return QualityRule("short", 40, 2, 1, False)
    if duration_seconds < 1800:
        return QualityRule("standard", 300, 5, 3, False)
    return QualityRule("long", 800, 8, 6, True)


def markdown_image_paths(text: str) -> list[str]:
    return [path.strip().replace("\\", "/") for path in re.findall(r"!\[[^]]*]\(([^)]+)\)", text)]


def load_figure_manifest(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict) or not isinstance(payload.get("figures"), list):
        raise ValueError("root must contain a figures array")
    records: list[dict] = []
    seen: set[str] = set()
    for item in payload["figures"]:
        if not isinstance(item, dict):
            raise ValueError("each figure must be an object")
        figure_path = item.get("path")
        timestamp = item.get("timestamp")
        if not isinstance(figure_path, str) or not FIGURE_PATH_PATTERN.fullmatch(figure_path):
            raise ValueError("figure path must match figures/figure_NNN.jpg")
        if figure_path in seen:
            raise ValueError("figure paths must be unique")
        if (
            not isinstance(timestamp, (int, float))
            or isinstance(timestamp, bool)
            or not math.isfinite(timestamp)
            or timestamp < 0
        ):
            raise ValueError("figure timestamp must be a non-negative finite number")
        if any(key in item and not isinstance(item[key], str) for key in ("section", "caption")):
            raise ValueError("figure section and caption must be strings")
        seen.add(figure_path)
        records.append(item)
    return records


def assess_notes(
    text: str,
    duration_seconds: float,
    source_signals: set[str],
    output_dir: Path,
) -> tuple[QualityRule, list[str]]:
    rule = quality_rule(duration_seconds)
    issues: list[str] = []
    cjk = sum("\u4e00" <= char <= "\u9fff" for char in text)
    sections = len(re.findall(r"^##\s+\S", text, re.MULTILINE))
    timestamps = len(re.findall(r"\b(?:\d{1,2}:)?\d{2}:\d{2}\b", text))
    if not re.search(r"^#\s+\S", text, re.MULTILINE):
        issues.append("notes.md must have a level-one title")
    if cjk < rule.minimum_cjk:
        issues.append(f"Chinese content is too short: {cjk} < {rule.minimum_cjk} CJK characters")
    if sections < rule.minimum_sections:
        issues.append(f"Too few sections: {sections} < {rule.minimum_sections}")
    if timestamps < rule.minimum_timestamps:
        issues.append(f"Too few source timestamps: {timestamps} < {rule.minimum_timestamps}")
    if rule.require_atom_audit:
        atom_path = output_dir / "teaching_atoms.tsv"
        if not atom_path.is_file():
            issues.append("Long videos require teaching_atoms.tsv")
        else:
            rows = [line.split("\t") for line in atom_path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
            if not rows or rows[0] != ["atom", "status", "evidence"]:
                issues.append("teaching_atoms.tsv must use atom/status/evidence columns")
            elif any(len(row) != 3 or row[1] != "ok" or not row[2].strip() for row in rows[1:]):
                issues.append("Every teaching atom must have status=ok and evidence")
    checks = {
        "formula": bool(re.search(r"\$\$.+?\$\$|\\\[.+?\\\]", text, re.DOTALL)),
        "code": "```" in text,
        "table": bool(re.search(r"^\|.+\|\s*$", text, re.MULTILINE)),
        "figure": bool(re.search(r"!\[[^]]*]\([^)]+\)", text)),
    }
    image_paths = markdown_image_paths(text)
    if any("contact" in path.casefold() for path in image_paths):
        issues.append("Contact sheets are analysis artifacts and cannot be embedded in notes.md")
    if any(not FIGURE_PATH_PATTERN.fullmatch(path) for path in image_paths):
        issues.append("Final note figures must use single-frame files under figures/")
    if any(FIGURE_PATH_PATTERN.fullmatch(path) and not (output_dir / path).is_file() for path in image_paths):
        issues.append("Every final note figure must exist under figures/")
    for signal in sorted(source_signals):
        if signal in checks and not checks[signal]:
            issues.append(f"Source contains {signal}, but notes.md does not")
    return rule, issues


def _run(command: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=300, check=False
        )
    except (OSError, subprocess.SubprocessError) as error:
        return False, str(error)
    detail = (result.stderr or result.stdout).strip()[-500:]
    return result.returncode == 0, detail


def write_manifest(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def render(
    source: Path,
    output_dir: Path,
    output_format: str,
    duration_seconds: float,
    platform_name: str,
    domain: str,
    provider: str,
    source_signals: set[str],
) -> tuple[int, dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    notes = output_dir / "notes.md"
    if source.resolve() != notes.resolve():
        shutil.copy2(source, notes)
    text = notes.read_text(encoding="utf-8-sig")
    rule, issues = assess_notes(text, duration_seconds, source_signals, output_dir)
    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "system": platform.platform(),
            "pandoc": shutil.which("pandoc"),
            "xelatex": shutil.which("xelatex"),
        },
        "platform": platform_name,
        "domain": domain,
        "provider": provider,
        "duration_seconds": duration_seconds,
        "quality_rule": asdict(rule),
        "source_signals": sorted(source_signals),
        "figures": [],
        "outputs": {"notes.md": {"status": "ready", "path": str(notes.resolve())}},
        "degraded": bool(issues),
        "degradation_reasons": issues,
    }
    figure_manifest = output_dir / "figure_manifest.json"
    if figure_manifest.is_file():
        try:
            manifest["figures"] = load_figure_manifest(figure_manifest)
        except (OSError, ValueError, json.JSONDecodeError):
            issues.append("figure_manifest.json is invalid")
    note_figure_paths = set(markdown_image_paths(text))
    manifest_figure_paths = {
        item["path"] for item in manifest["figures"] if isinstance(item, dict) and "path" in item
    }
    if note_figure_paths and not figure_manifest.is_file():
        issues.append("notes.md figures require figure_manifest.json")
    elif note_figure_paths != manifest_figure_paths:
        issues.append("notes.md figure references must match figure_manifest.json")
    manifest["degraded"] = bool(issues)
    manifest_path = output_dir / "run_manifest.json"
    if issues:
        write_manifest(manifest_path, manifest)
        return 2, manifest

    requested = {output_format} if output_format != "all" else {"latex", "pdf"}
    if "latex" in requested:
        target = output_dir / "notes.tex"
        pandoc = shutil.which("pandoc")
        if not pandoc:
            issues.append("Pandoc is required for notes.tex")
            manifest["outputs"]["notes.tex"] = {"status": "unavailable"}
        else:
            ok, detail = _run([pandoc, str(notes), "--standalone", "-o", str(target)])
            if ok and target.is_file():
                manifest["outputs"]["notes.tex"] = {"status": "ready", "path": str(target.resolve())}
            else:
                issues.append(f"Pandoc LaTeX conversion failed: {detail}")
                manifest["outputs"]["notes.tex"] = {"status": "failed"}
    if "pdf" in requested:
        target = output_dir / "notes.pdf"
        pandoc, xelatex = shutil.which("pandoc"), shutil.which("xelatex")
        if not pandoc or not xelatex:
            issues.append("Pandoc and XeLaTeX are required for notes.pdf")
            manifest["outputs"]["notes.pdf"] = {"status": "unavailable"}
        else:
            ok, detail = _run(
                [pandoc, str(notes), "--standalone", "--pdf-engine=xelatex", "-o", str(target)]
            )
            if ok and target.is_file():
                manifest["outputs"]["notes.pdf"] = {"status": "ready", "path": str(target.resolve())}
            else:
                issues.append(f"PDF conversion failed: {detail}")
                manifest["outputs"]["notes.pdf"] = {"status": "failed"}
    manifest["degraded"] = bool(issues)
    manifest["degradation_reasons"] = issues
    write_manifest(manifest_path, manifest)
    return (1 if issues else 0), manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--format", choices=("markdown", "latex", "pdf", "all"), default="markdown")
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--platform", default="unknown")
    parser.add_argument("--domain", default="general")
    parser.add_argument("--provider", default="none")
    parser.add_argument(
        "--source-signals",
        default="",
        help="Comma-separated source evidence: formula,code,table,figure",
    )
    args = parser.parse_args()
    signals = {item.strip() for item in args.source_signals.split(",") if item.strip()}
    unknown = signals - {"formula", "code", "table", "figure"}
    if unknown:
        parser.error(f"unknown source signals: {', '.join(sorted(unknown))}")
    code, manifest = render(
        args.input,
        args.output_dir,
        args.format,
        args.duration,
        args.platform,
        args.domain,
        args.provider,
        signals,
    )
    if manifest["degraded"]:
        for reason in manifest["degradation_reasons"]:
            print(reason, file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())

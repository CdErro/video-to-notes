#!/usr/bin/env python3
"""Merge seed glossaries and safely learn evidenced subtitle corrections."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import time
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SEED_ROOT = ROOT / "glossaries"
DEFAULT_USER_ROOT = Path.home() / ".video-to-notes" / "glossaries"
DOMAIN_HINTS = {
    "nju-os": {
        "操作系统",
        "系统调用",
        "kernel",
        "fork",
        "execve",
        "南京大学",
        "jyy",
        "蒋炎岩",
    }
}


def normalize_term(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().casefold()


def validate_domain(domain: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", domain or ""):
        raise ValueError(f"Invalid glossary domain: {domain!r}")
    return domain


def detect_domains(context: str) -> list[str]:
    normalized = normalize_term(context)
    selected = [
        domain
        for domain, hints in DOMAIN_HINTS.items()
        if sum(normalize_term(hint) in normalized for hint in hints) >= 2
    ]
    return ["general", *selected]


def _read_glossary(path: Path, domain: str) -> dict:
    if not path.exists():
        return {"schema_version": 1, "domain": domain, "entries": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("entries"), dict):
        raise ValueError(f"Unsupported glossary format: {path}")
    return payload


def load_entries(domains: list[str], user_root: Path = DEFAULT_USER_ROOT) -> dict[str, dict]:
    merged: dict[str, dict] = {}
    normalized: dict[str, str] = {}
    for domain in domains:
        validate_domain(domain)
        for path in (SEED_ROOT / f"{domain}.json", user_root / f"{domain}.json"):
            for original, entry in _read_glossary(path, domain)["entries"].items():
                key = normalize_term(original)
                replacement = str(entry.get("replacement", "")).strip()
                if not key or not replacement:
                    continue
                if key in normalized and normalize_term(merged[normalized[key]]["replacement"]) != normalize_term(replacement):
                    continue
                normalized[key] = original
                merged[original] = entry
    return merged


def replacements(domains: list[str], user_root: Path = DEFAULT_USER_ROOT) -> dict[str, str]:
    return {
        original: str(entry["replacement"])
        for original, entry in load_entries(domains, user_root).items()
    }


def build_prompt(context: str, domains: list[str] | None = None, user_root: Path = DEFAULT_USER_ROOT) -> str:
    selected = domains or detect_domains(context)
    terms = sorted({*replacements(selected, user_root).keys(), *replacements(selected, user_root).values()})
    prefix = f"这是{context or '一个通用视频'}的录音。"
    return prefix + (" 重点词汇：" + "、".join(terms) + "。" if terms else "")


def parse_srt_text(path: Path) -> dict[int, str]:
    result: dict[int, str] = {}
    for block in re.split(r"\r?\n\r?\n+", path.read_text(encoding="utf-8-sig").strip()):
        lines = block.splitlines()
        if len(lines) >= 3 and lines[0].strip().isascii() and lines[0].strip().isdigit():
            result[int(lines[0])] = "\n".join(lines[2:]).strip()
    return result


@contextmanager
def glossary_lock(root: Path, timeout: float = 10.0):
    root.mkdir(parents=True, exist_ok=True)
    path = root / ".update.lock"
    handle = path.open("a+b")
    handle.seek(0, os.SEEK_END)
    if handle.tell() == 0:
        handle.write(b"0")
        handle.flush()
    deadline = time.monotonic() + timeout
    while True:
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except (BlockingIOError, OSError):
            if time.monotonic() >= deadline:
                handle.close()
                raise TimeoutError(f"Glossary is locked: {path}")
            time.sleep(0.05)
    try:
        yield
    finally:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        for attempt in range(3):
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 2:
                    raise
                time.sleep(0.05 * (attempt + 1))
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def update_glossary(
    raw: dict[int, str],
    corrected: dict[int, str],
    candidates: list[dict],
    domain: str,
    user_root: Path = DEFAULT_USER_ROOT,
    audit_path: Path | None = None,
) -> dict:
    validate_domain(domain)
    audit = {
        "schema_version": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "domain": domain,
        "added": [],
        "conflicts": [],
        "rejected": [],
    }
    with glossary_lock(user_root):
        user_path = user_root / f"{domain}.json"
        user_data = _read_glossary(user_path, domain)
        existing = load_entries(["general", domain], user_root)
        by_normalized = {normalize_term(key): value for key, value in existing.items()}
        for candidate in candidates:
            original = str(candidate.get("original", "")).strip()
            replacement = str(candidate.get("corrected", "")).strip()
            indices = candidate.get("indices")
            reason = ""
            if not original or not replacement or normalize_term(original) == normalize_term(replacement):
                reason = "empty_or_unchanged"
            elif not isinstance(indices, list) or not indices or not all(type(index) is int for index in indices):
                reason = "invalid_indices"
            elif not all(
                original in raw.get(index, "")
                and replacement in corrected.get(index, "")
                and raw.get(index) != corrected.get(index)
                and corrected.get(index, "").count(original) < raw.get(index, "").count(original)
                for index in indices
            ):
                reason = "evidence_mismatch"
            key = normalize_term(original)
            current = by_normalized.get(key)
            if not reason and current and normalize_term(current["replacement"]) != normalize_term(replacement):
                audit["conflicts"].append(
                    {"original": original, "candidate": replacement, "existing": current["replacement"]}
                )
                continue
            if reason:
                audit["rejected"].append({"candidate": candidate, "reason": reason})
                continue
            if current:
                continue
            entry = {
                "replacement": replacement,
                "evidence": [
                    {
                        "srt_index": index,
                        "raw_text": raw[index],
                        "corrected_text": corrected[index],
                    }
                    for index in indices
                ],
                "updated_at": audit["timestamp"],
            }
            user_data["entries"][original] = entry
            by_normalized[key] = entry
            audit["added"].append(
                {
                    "original": original,
                    "corrected": replacement,
                    "indices": indices,
                    "evidence": entry["evidence"],
                }
            )
        _atomic_json(user_path, user_data)
        _atomic_json(audit_path or user_root / "glossary_update.json", audit)
    return audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prompt = commands.add_parser("prompt")
    prompt.add_argument("--context", default="")
    prompt.add_argument("--domain", action="append")
    prompt.add_argument("--root", type=Path, default=DEFAULT_USER_ROOT)
    update = commands.add_parser("update")
    update.add_argument("--raw-srt", type=Path, required=True)
    update.add_argument("--corrected-srt", type=Path, required=True)
    update.add_argument("--candidates", type=Path, required=True)
    update.add_argument("--domain", default="general")
    update.add_argument("--root", type=Path, default=DEFAULT_USER_ROOT)
    update.add_argument("--audit", type=Path)
    args = parser.parse_args()
    if args.command == "prompt":
        print(build_prompt(args.context, args.domain, args.root))
        return 0
    candidates = json.loads(args.candidates.read_text(encoding="utf-8"))
    audit = update_glossary(
        parse_srt_text(args.raw_srt),
        parse_srt_text(args.corrected_srt),
        candidates,
        args.domain,
        args.root,
        args.audit,
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 1 if audit["conflicts"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

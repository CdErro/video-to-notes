#!/usr/bin/env python3
"""Detect and metadata-probe lecture video sources."""

import argparse
import json
import math
import re
import subprocess
import sys
from collections.abc import Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class UnsupportedSourceError(ValueError):
    """Raised when a URL is not a supported lecture video source."""


class ProbeError(RuntimeError):
    """Raised when yt-dlp cannot validate a playable source."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _normalized_host(host: str) -> str:
    normalized = host.lower().rstrip(".")
    for prefix in ("www.", "mobile.", "m."):
        if normalized.startswith(prefix):
            return normalized[len(prefix) :]
    return normalized


def detect_platform(url: str) -> str:
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        _ = parsed.port
    except ValueError as error:
        raise UnsupportedSourceError(f"Unsupported video URL: {url}") from error

    if parsed.scheme not in ("http", "https") or not hostname:
        raise UnsupportedSourceError(f"Unsupported video URL: {url}")

    host = _normalized_host(hostname)
    path = parsed.path.rstrip("/")

    if host == "youtu.be" and re.fullmatch(r"/[A-Za-z0-9_-]+", path):
        return "youtube"

    if host == "youtube.com" or host.endswith(".youtube.com"):
        video_ids = parse_qs(parsed.query, keep_blank_values=True).get("v", [])
        if path == "/watch" and len(video_ids) == 1 and re.fullmatch(
            r"[A-Za-z0-9_-]+", video_ids[0]
        ):
            return "youtube"
        if re.fullmatch(r"/(?:live|shorts|embed)/[A-Za-z0-9_-]+", path):
            return "youtube"

    if host == "b23.tv" and path:
        return "bilibili"

    if (
        host == "bilibili.com" or host.endswith(".bilibili.com")
    ) and re.fullmatch(r"/video/BV[0-9A-Za-z]+", path, re.IGNORECASE):
        return "bilibili"

    if host in ("x.com", "twitter.com") and re.fullmatch(
        r"/[^/]+/status/[0-9]+(?:/video/[0-9]+)?", path
    ):
        return "x"

    if host == "xhslink.com" and path:
        return "xiaohongshu"

    if (host == "xiaohongshu.com" or host.endswith(".xiaohongshu.com")) and re.fullmatch(
        r"/(?:explore|discovery/item)/[0-9A-Fa-f]+", path
    ):
        return "xiaohongshu"

    raise UnsupportedSourceError(f"Unsupported video URL: {url}")


def _subtitle_languages(payload: dict) -> list[str]:
    languages = set()
    for field in ("subtitles", "automatic_captions"):
        tracks = payload.get(field)
        if tracks is None:
            continue
        if not isinstance(tracks, Mapping):
            raise ProbeError(
                f"yt-dlp returned invalid {field} metadata; expected an object"
            )
        languages.update(tracks.keys())
    return sorted(languages)


def _is_xiaohongshu_host(url: str, *, include_short: bool = True) -> bool:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    host = _normalized_host(parsed.hostname or "")
    return parsed.scheme in ("http", "https") and (
        (include_short and host == "xhslink.com")
        or host == "xiaohongshu.com"
        or host.endswith(".xiaohongshu.com")
    )


def _redirect_location(url: str) -> str | None:
    opener = build_opener(_NoRedirect)
    request = Request(url, headers={"User-Agent": "video-to-notes/1"}, method="GET")
    try:
        with opener.open(request, timeout=10):
            return None
    except HTTPError as error:
        if 300 <= error.code < 400 and error.headers.get("Location"):
            return urljoin(url, error.headers["Location"])
        raise ProbeError(f"小红书短链请求失败：HTTP {error.code}") from error
    except URLError as error:
        raise ProbeError(f"小红书短链请求失败：{error.reason}") from error


def resolve_xiaohongshu_url(url: str, max_redirects: int = 5) -> str:
    """Resolve a short link without ever following a redirect to another service."""
    current = url
    for _ in range(max_redirects + 1):
        if not _is_xiaohongshu_host(current):
            raise ProbeError("小红书短链重定向到了非官方域名，已拒绝访问")
        if _normalized_host(urlsplit(current).hostname or "") != "xhslink.com":
            if detect_platform(current) != "xiaohongshu":
                raise ProbeError("小红书短链未指向可识别的视频页面")
            parsed = urlsplit(current)
            return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
        location = _redirect_location(current)
        if location is None:
            raise ProbeError("小红书短链没有返回目标视频地址")
        current = location
    raise ProbeError("小红书短链重定向次数过多")


def _compact_metadata(
    platform: str, payload: dict, *, original_url: str = "", canonical_url: str = ""
) -> dict:
    if not isinstance(payload, Mapping):
        raise ProbeError("yt-dlp metadata must be a JSON object")

    source_id = str(payload.get("id") or "").strip()
    if not source_id:
        raise ProbeError("yt-dlp returned no playable video ID")

    duration = payload.get("duration")
    if (
        type(duration) not in (int, float)
        or not math.isfinite(duration)
        or duration <= 0
    ):
        raise ProbeError("yt-dlp returned no positive video duration")

    metadata = {
        "platform": platform,
        "id": source_id,
        "title": payload.get("title") or "",
        "uploader": payload.get("uploader") or "",
        "duration": float(duration),
        "webpage_url": payload.get("webpage_url") or "",
        "has_thumbnail": bool(payload.get("thumbnail")),
        "subtitle_languages": _subtitle_languages(payload),
    }
    if platform == "xiaohongshu":
        metadata["original_url"] = original_url
        metadata["canonical_url"] = canonical_url
    return metadata


def probe_source(url: str, *, cookies_from_browser: str | None = None) -> dict:
    platform = detect_platform(url)
    canonical_url = (
        resolve_xiaohongshu_url(url)
        if platform == "xiaohongshu" and _normalized_host(urlsplit(url).hostname or "") == "xhslink.com"
        else url
    )
    command = [
        "yt-dlp",
        "--dump-single-json",
        "--no-playlist",
        "--skip-download",
    ]
    if cookies_from_browser:
        command.extend(["--cookies-from-browser", cookies_from_browser])
    command.append(canonical_url)

    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, check=False
        )
    except FileNotFoundError as error:
        raise ProbeError("yt-dlp executable was not found") from error

    if completed.returncode != 0:
        detail = completed.stderr.strip() or "unknown extractor failure"
        raise ProbeError(f"yt-dlp probe failed: {detail}")

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise ProbeError("yt-dlp returned invalid JSON metadata") from error

    if platform == "xiaohongshu" and not payload.get("formats"):
        raise ProbeError("该小红书页面不包含可下载视频；纯图文笔记不受支持")

    return _compact_metadata(
        platform, payload, original_url=url, canonical_url=canonical_url
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    detect_parser = subparsers.add_parser("detect")
    detect_parser.add_argument("url")

    probe_parser = subparsers.add_parser("probe")
    probe_parser.add_argument("url")
    probe_parser.add_argument("--cookies-from-browser")

    args = parser.parse_args()

    try:
        if args.command == "detect":
            print(detect_platform(args.url))
        else:
            print(
                json.dumps(
                    probe_source(
                        args.url, cookies_from_browser=args.cookies_from_browser
                    ),
                    ensure_ascii=False,
                    indent=2,
                )
            )
    except UnsupportedSourceError as error:
        print(error, file=sys.stderr)
        return 2
    except ProbeError as error:
        print(error, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

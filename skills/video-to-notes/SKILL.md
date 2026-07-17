---
name: video-to-notes
description: Convert YouTube, Bilibili, X/Twitter, or Xiaohongshu videos into evidence-based Chinese Markdown notes, with optional LaTeX/PDF output, subtitle correction, adaptive glossaries, and run manifests. Use when a user asks for video notes, 视频转笔记, 视频总结, 讲义, Markdown, or PDF from a supported video URL or local media.
---

# Video to Notes

Produce Chinese `notes.md` from the source video. Preserve the old `lecture-to-notes`
workflow only for compatibility; use this skill for new work.

## Resolve the repository

This repository-backed skill calls helpers under `<repo>/scripts`. Resolve `<repo>` as
the directory two levels above this loaded `SKILL.md`. Use absolute paths in commands.
Read [quality-rules.md](references/quality-rules.md) before drafting notes.

## 1. Check the environment

Run a read-only check for the requested output and Provider:

```powershell
conda run -n vid2rich python <repo>/scripts/environment.py doctor --json --format markdown --provider kimi-cli
```

Use `setup.ps1` or `setup.sh` only after the user authorizes installation. Never install
Python packages into system Python. Markdown needs Python, `yt-dlp`, FFmpeg/ffprobe, and
the selected Provider. LaTeX/PDF additionally need Pandoc; PDF needs XeLaTeX.

## 2. Inspect and acquire the source

Probe before downloading:

```powershell
conda run -n vid2rich python <repo>/scripts/video_source.py probe "<URL>"
```

Supported sources are YouTube, Bilibili, X/Twitter, and Xiaohongshu. For Xiaohongshu,
short-link redirects must stay on official domains and image-only notes are unsupported.
Use `--cookies-from-browser <browser>` only when needed; never save or copy cookies.

Download metadata, thumbnail, audio, and video with `yt-dlp --no-playlist`. For a
multi-part Bilibili item, list parts and ask which part to process. Store all artifacts
under `runs/<run-name>/`; do not commit them.

## 3. Prepare evidence

Use a healthy supplied caption track when available. Otherwise extract audio and run
Whisper with a prompt built from the general glossary and the detected domain:

```powershell
conda run -n vid2rich python <repo>/scripts/glossary.py prompt --context "<video context>"
```

Apply deterministic corrections, then optionally run semantic correction:

```powershell
conda run -n vid2rich python <repo>/scripts/correct_srt.py audio.srt --context "<video context>" --stats
conda run -n vid2rich python <repo>/scripts/llm_correct_srt.py --srt audio.srt --frames frames --out audio_corrected.srt --context "<video context>" --provider kimi-cli
```

For OpenAI, add `--provider openai --model <model> --env-file .env`. Read only
`OPENAI_API_KEY` and optional `OPENAI_BASE_URL`. Provider failure must retry three times,
then preserve the original subtitle without switching Provider. Keep
`glossary_update.json`; conflicts never overwrite existing entries.

## 4. Draft `notes.md`

Start from [notes-outline.md](assets/notes-outline.md). Write in Chinese and reconstruct
the teaching flow instead of copying subtitle order. Every substantive claim needs a
timestamp or verified frame. Exclude greetings, promotions, and repeated filler.

Include formulas, code, tables, and figures only when they occur in the source. When they
do occur, represent them faithfully and pass the matching `--source-signals` value to the
quality check. Never invent a diagram, equation, example, or conclusion.

## 5. Validate and render

Always deliver Markdown. Request other formats only when needed:

```powershell
conda run -n vid2rich python <repo>/scripts/render_notes.py draft.md --output-dir runs/<run-name> --duration <seconds> --platform <platform> --domain <domain> --provider <provider> --format markdown --source-signals "formula,code,table,figure"
```

- `markdown`: writes `notes.md`.
- `latex`: additionally writes `notes.tex` through Pandoc.
- `pdf`: additionally writes `notes.pdf` through Pandoc + XeLaTeX.
- `all`: writes all three.

Remove signals not present in the source; do not use signal omission to bypass detected
source content. A failed quality check still preserves `notes.md` and records why the run
degraded. Fix the notes and rerun rather than claiming completion.

## 6. Deliver

Verify `run_manifest.json` records the environment, platform, domain, Provider, quality
tier, outputs, and degradation state. Return absolute paths to `notes.md`, optional
rendered files, `run_manifest.json`, and `glossary_update.json` when correction ran.

# Repository Guidelines

## Project Structure & Module Organization

Core Python utilities live in `scripts/`; prompt and glossary data belongs in `scripts/whisper_prompts/`. Reusable skill definitions and LaTeX assets are under `skills/lecture-to-notes/` and `skills/paper-to-html/`. Published content is stored in `docs/`: edit `docs/index.html` for the catalog, place lecture PDFs in `docs/pdfs/`, and keep paper pages and images in `docs/papers/`. Tests live in `tests/` and generally mirror a script or documentation contract.

## Build, Test, and Development Commands

This repository has no package build step. Use Python 3 from the repository root:

```bash
python -m unittest discover -s tests -v
python scripts/video_source.py detect "<URL>"
python scripts/video_source.py probe "<URL>"
python scripts/check_srt_health.py captions.srt --duration 3600
```

The first command runs all tests. The others exercise source detection, `yt-dlp` metadata probing, and subtitle validation. A full lecture run also requires `yt-dlp`, `ffmpeg`, ImageMagick, Whisper, and `xelatex`; see `README.md` for installation.

## Coding Style & Naming Conventions

Follow existing Python style: four-space indentation, standard-library imports before local imports, `snake_case` for functions and variables, and `PascalCase` for exceptions and test classes. Add type hints to public helpers when practical and keep CLI entry points in `main()`. Use `pathlib.Path` for filesystem work and report external-command failures with actionable errors. No formatter or linter is configured, so avoid unrelated formatting changes. Name tests `test_<behavior>` in files named `test_<module>.py`.

## Testing Guidelines

Tests use Python's `unittest` and `unittest.mock`. Add success, invalid-input, and external-tool failure cases for changed scripts. Documentation and skill edits may require contract tests because commands and wording are executable project behavior. No numeric coverage threshold is enforced; cover every changed branch. Some shell smoke tests require `zsh` and skip or fail clearly when it is unavailable.

## Commit & Pull Request Guidelines

Use the repository's Conventional Commit pattern, such as `feat(skill): add source support`, `fix: reject malformed timestamps`, or `docs: update workflow`. Keep each commit focused. Pull requests should explain the user-visible change, list verification commands, link the relevant issue, and update `README.md` or `RELEASE_NOTES.md` when behavior changes. Include screenshots only for changes to `docs/index.html` or generated visual output; do not commit temporary downloads, transcripts, or build artifacts.

## Security & Configuration

Do not commit API keys, cookies, login exports, or private media. Preserve complete user-supplied URLs only where required for processing, and sanitize fixtures and logs before committing.

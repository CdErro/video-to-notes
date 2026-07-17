# Repository Guidelines

## Project Structure & Module Organization

Core Python utilities live in `scripts/`; adaptive glossary seeds are in
`scripts/glossaries/`, while legacy Whisper prompts remain in
`scripts/whisper_prompts/`. Reusable workflows live under `skills/`, with
`skills/video-to-notes/` as the current entry and `skills/lecture-to-notes/` retained
for compatibility. Tests in `tests/` mirror script or Skill behavior. Design records
belong in `design/`. Generated media and notes must stay under ignored `runs/` or
`artifacts/` directories.

## Build, Test, and Development Commands

Use the local Conda environment for every Python command:

```powershell
conda run -n vid2rich python scripts/environment.py doctor --json
conda run -n vid2rich python -m unittest discover -s tests -v
conda run -n vid2rich python scripts/video_source.py probe "<URL>"
conda run -n vid2rich python scripts/render_notes.py draft.md --output-dir runs/demo --duration 120
```

`doctor` checks required tools without modifying the machine. The test command runs the
full `unittest` suite. Source probing validates metadata through `yt-dlp`; rendering
always writes `notes.md` and optionally invokes Pandoc/XeLaTeX.

## Coding Style & Naming Conventions

Use four-space indentation, standard-library imports before local imports, `snake_case`
for functions and variables, and `PascalCase` for classes and exceptions. Prefer
`pathlib.Path`, type public helpers where practical, and put CLI execution behind
`main()` with a meaningful exit code. External IO and subprocess failures must be
actionable; never silently switch providers or swallow errors. No formatter is
configured, so avoid unrelated reformatting.

## Testing Guidelines

Tests use `unittest` and `unittest.mock`. Name files `test_<module>.py` and methods
`test_<behavior>`. Cover success, invalid input, degraded behavior, and external-tool
failure paths. Mock installers, network calls, Kimi, OpenAI, Pandoc, and XeLaTeX; never
use real credentials in automated tests. Run the full suite before every PR.

## Commit & Pull Request Guidelines

Follow Conventional Commits, for example `feat: support source`, `fix: reject unsafe
redirect`, or `docs: update workflow`. Keep commits focused. PRs target `tool-only`,
describe user-visible changes, list verification commands, and link relevant issues.
Each feature PR requires an independent review before merge; `main` remains an upstream
mirror and must not receive customization commits.

## Security & Configuration

Never commit `.env`, API keys, cookies, private media, transcripts, or generated notes.
Read OpenAI settings only from `OPENAI_API_KEY` and optional `OPENAI_BASE_URL`. Preserve
`LICENSE`, upstream attribution, and the unrevised Git history.

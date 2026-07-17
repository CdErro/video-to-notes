#!/usr/bin/env sh
set -eu

TARGET="${VIDEO_TO_NOTES_TARGET:-conda:video-to-notes}"
if command -v conda >/dev/null 2>&1; then
  exec conda run -n base python "$(dirname "$0")/scripts/environment.py" install --target "$TARGET" --with-transcription "$@"
elif command -v python3 >/dev/null 2>&1; then
  exec python3 "$(dirname "$0")/scripts/environment.py" install --target "${VIDEO_TO_NOTES_TARGET:-venv:.venv}" --with-transcription "$@"
else
  echo "Python 3.11+ or Conda is required to run setup." >&2
  exit 1
fi

# Quality Rules

The renderer selects a tier from the probed video duration.

| Duration | Tier | Minimum CJK | `##` sections | timestamps | Extra evidence |
|---|---|---:|---:|---:|---|
| `<5 min` | short | 40 | 2 | 1 | none |
| `5–30 min` | standard | 300 | 5 | 3 | none |
| `≥30 min` | long | 800 | 8 | 6 | `teaching_atoms.tsv` |

These are minimum rejection gates, not writing targets. Cover every distinct teaching
point even when the minimum has already been met. Each timestamp must support the nearby
claim. For long videos, `teaching_atoms.tsv` uses `atom<TAB>status<TAB>evidence`; every
row must map a source concept to a note section or timestamp.

Source-conditional checks are mandatory:

- source formula → Markdown display formula;
- source code → fenced code block;
- source comparison/table → Markdown table;
- source visual evidence → embedded verified figure.

Do not add any of these merely to satisfy a count. If the source has none, omit it and do
not pass that signal to the renderer.

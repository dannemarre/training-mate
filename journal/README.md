# Training journal

Two files per ISO week, both committed to git so the diary survives across machines.

- `YYYY-WW-plan.md` — written **before** the week. The proposed schedule + rationale. Source of truth for what gets pushed to Google Calendar.
- `YYYY-WW-log.md` — written **during** the week. Daily notes (planned vs actual, RPE, knee, sleep, mood). At week-end Claude appends a retrospective.

Naming: ISO week. e.g. `2026-17-plan.md` is week 17 of 2026 (Apr 20–26 in Europe/Stockholm). `date '+%G-%V'` returns the ISO year-week pair Claude should use.

## Conventions

- One H1 at top: `# Week N, YYYY (Mon DD – Sun DD)`.
- Use the templates in this directory:
  - `_template-plan.md` — copy when Claude writes `/plan-week`.
  - `_template-log.md` — copy when Claude writes `/log` for the first time in a week.
- Edit in place during the week; never overwrite. If a session moves, update the plan file and note the change in the log.
- All times Europe/Stockholm.

## How Claude uses these

- `/plan-week` reads `tools/current_form.py`, last 14 days from `tools/list_activities.py`, and `docs/group-rides.md`, then writes `YYYY-WW-plan.md` from `_template-plan.md`. It then offers a Google Calendar diff for confirmation.
- `/log` reads today's date, opens or creates `YYYY-WW-log.md` from `_template-log.md`, and appends to the right day section.
- `/review` reads both files for the week, summarises planned-vs-done, and appends a retrospective to the log.

The log is the single most important artefact for the trainer to learn Martin's patterns over time. Be honest in it.

---
description: Today's wind-ranked KOM-attack segments. Delegates to the kom-hunter subagent. Use for "/kom", "any KOMs today?", "wind-favorable segments", or pre-ride opportunity scanning.
---

# /kom

Surface the top wind-favorable starred segments for the next 6 hours, with a realistic-threat read.

## Steps

1. **Make sure segments are synced**:
   ```
   uv run python tools/sync_segments.py --limit 50
   ```
   (Skip if `segments` table already populated from a recent sync.)

2. **Delegate to the `kom-hunter` subagent.** The subagent will:
   - Run `tools/kom_today.py --top 5 --hours-ahead 6`.
   - Drill in with `tools/kom_threat.py` for borderline cases.
   - Cross-check Martin's `current_form.py` (skip max efforts if overreached/risky).
   - Cross-check knee status via daily_briefing / recent journal.
   - Return a 3-5 line ranked list.

3. **Surface the result.** Clean output, no JSON. Citations to `docs/wind-and-kom.md` for the threat-threshold formula.

## Constraints

- Don't recommend max efforts if `form_state` is `risky`, `overreached`, or `crashing`.
- Don't recommend out-of-saddle KOM attempts if knee is yellow/red.
- Cite `docs/wind-and-kom.md` for any non-obvious math.
- If `kom_today.py` returns no segments, suggest `sync_segments.py` first; don't fabricate.

---
description: Honest weekly retrospective — diff plan vs actual, surface lessons, persist them for next week's planning. Delegates to the weekly-reviewer subagent. Use for "/review", end-of-week reflections.
---

# /review

Run on Sunday evening (or the start of the next week). Produces an honest plan-vs-actual retro and writes it to the week's log file.

## Steps

1. **Make sure data is current**:
   ```
   uv run python tools/sync_activities.py --since "$(date -u -v-7d +%Y-%m-%d)"
   uv run python tools/compute_pmc.py
   ```

2. **Delegate to the `weekly-reviewer` subagent.** It runs `tools/weekly_review.py`, reads plan + log, cross-checks trends, and composes the retrospective.

3. **Surface the retro** in chat AND confirm it landed in `journal/YYYY-WW-log.md` under `## Weekly review`.

4. **Persist lessons** — the subagent appends concise lessons to `.claude/agent-memory/coach/MEMORY.md`. These inform next week's `/plan-week`.

## Constraints

- Honesty over politeness (CLAUDE.md tone).
- Cite docs for any trend-based call.
- Don't rewrite earlier daily entries — append only.
- If the journal log is sparse, say so once and don't extrapolate.

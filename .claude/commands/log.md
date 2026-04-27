---
description: Append today's training note to journal/YYYY-WW-log.md.
---

# /log

Append a daily training entry to the current week's log file. Used after a session, or end-of-day.

## Steps

1. **Resolve the file.** Compute today's ISO week with `date '+%G-%V'` → file is `journal/YYYY-WW-log.md`. If it doesn't exist, create it from `journal/_template-log.md` and fill the seven date headings for this week (Mon-Sun, Europe/Stockholm).

2. **Find today's section.** It's `## <Day> YYYY-MM-DD`. If today's heading still has placeholders, fill them. If a session has already been logged today, append a sub-bullet rather than overwriting.

3. **Gather the data.** Prefer in this order:
   - If there's a freshly recorded Strava activity from today: use `tools/get_activity.py --id <id>` to fetch duration, TSS, IF, kJ, avg HR. (When this lands.)
   - Otherwise ask Martin: planned vs done, RPE, sleep last night, knee before/after, free-form notes.
   - Knee score is non-negotiable — always ask if not provided.

4. **Write.** Use Edit on `journal/YYYY-WW-log.md` to fill today's section. Don't rewrite earlier days.

5. **Flag patterns.** If knee score has trended worse for two consecutive days, surface a one-line warning at the top of your reply suggesting a rehab-only day or a check with the physio.

## Constraints

- Don't overwrite previous entries. Append.
- Don't change the planning file (`journal/YYYY-WW-plan.md`) from `/log`. If a session moved, note the move in the log; planning changes happen via `/plan-week`.
- Times Europe/Stockholm.

---
description: Full daily briefing — readiness, plan, weather, fueling for tomorrow's ride. Heavier than /today; especially valuable for long-ride days (Sat→Sun Ängby) and race weeks. Use when Martin says "/brief" or asks for tomorrow's full plan.
---

# /brief

Like `/today` but with the next-24-hour preview built in: weather, route, fueling. Especially useful Saturday evening for the Sunday Ängby söndag.

## Steps

1. **Today's briefing** (re-use the daily aggregator):
   ```
   uv run python tools/daily_briefing.py
   ```

2. **Tomorrow's planned session** — read the next row from `journal/YYYY-WW-plan.md`. If today is Saturday and tomorrow is Sunday Ängby söndag, treat it as the priority — the rest of this skill focuses there.

3. **Weather window** for tomorrow's ride hours:
   ```
   uv run python tools/route_weather.py --lat 59.342 --lon 18.005 --hours-ahead 24
   ```
   (Use Martin's planned start location — ask if uncertain. Default Stockholm centre.)

4. **Delegate to `fueling-advisor` subagent** for any ride longer than 90 min OR with IF > 0.85. The subagent reads the planned session + weather and produces the per-hour plan.

5. **Compose the response** in 3 sections:

   **Now (today):**
   - Form / wellness summary (same shape as `/today`).
   - Today's planned session and one concrete recommendation.

   **Tomorrow's preview:**
   - Planned session + duration.
   - Weather window (key hours, temp range, wind, precip).
   - Fueling plan (per-hour grid, pre, post). From the fueling subagent if delegated.

   **Decision points:**
   - Anything Martin should confirm (knee score, ride start time, refuel stops).

## Constraints

- Don't repeat citations from `/today` if you just used them — but if you cite a *new* doc (e.g. `docs/fueling.md`) for tomorrow's prep, do.
- Hot day (temp > 25): lead with the fueling adjustments.
- If knee yellow/red today AND tomorrow is hard: propose a swap now (don't wait until morning).
- Per CLAUDE.md rule #4 — never push tomorrow's workout to Garmin without confirmation.

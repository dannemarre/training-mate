---
description: Show Martin's current training form (CTL/ATL/TSB) and what it means. Use when Martin asks about readiness, form, fitness, fatigue, or "how am I doing?".
---

# /form

Quick read-out of Martin's PMC state. Cite `docs/training-science.md` when explaining the call.

## Steps

1. **Make sure PMC is fresh.** If activities were synced recently, run:
   ```
   uv run python tools/compute_pmc.py
   ```
   Otherwise skip.

2. **Read current form:**
   ```
   uv run python tools/current_form.py
   ```

3. **Translate the JSON for Martin** in 3-4 short bullets:
   - The `form_state` and what it means in plain English. Use the bands from `docs/training-science.md#tsb-interpretation-thresholds`. Example: *"You're at TSB +12, **race-ready** (+5..+20 band per training-science.md). Productive build territory just behind you — fitness landed cleanly."*
   - The 7-day CTL ramp and whether it's safe (`ramp_7d ≤ +8` per training-science.md). Quote the number.
   - One sentence on what to consider for today's session given the form. Don't prescribe a workout — that's `/today`'s job — but hint: e.g. *"Form is fresh, so a Z4 session today fits. If knee is green, anything in the workout-library.md threshold or VO2 sections is fair game."*

4. **If `ramp_warning=true`**: surface that immediately at the top. Example: *"⚠️ Ramp +9.3 in the last 7 days — at the warning ceiling per training-science.md. Don't increase load further this week."*

5. **If `ramp_critical=true`**: stronger warning. *"🚨 Ramp +12 sustained — crash territory per docs. Recommend a recovery week now."*

## Constraints

- Do not recommend a specific workout in this skill — keep it to form interpretation.
- Always cite `docs/training-science.md`.
- If the JSON contains an error (e.g. "pmc_daily is empty"), surface that and recommend `compute_pmc.py --backfill` rather than guessing.

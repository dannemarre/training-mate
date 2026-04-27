---
description: Sync Strava activities (and optionally Garmin wellness) into the local cache, then refresh PMC. Use when Martin says /sync, "pull latest", "did my ride land?", or after a recent ride.
---

# /sync

Pull recent activities and wellness data, then refresh form metrics so subsequent skills (`/today`, `/form`, `/plan-week`) see the latest.

## Steps

1. **Pull activities + wellness** (last 7 days by default; offer wider window if Martin asks):
   ```
   uv run python tools/sync_activities.py --since "$(date -u -v-7d +%Y-%m-%d)" --include-wellness
   ```

   If only activities are needed (e.g. Garmin's down or rate-limited): drop `--include-wellness`. If only wellness: add `--no-strava`.

2. **Refresh PMC** so form numbers are current:
   ```
   uv run python tools/compute_pmc.py
   ```

3. **Report** in 2–4 short lines:
   - What synced (e.g. *"3 new Strava activities, 7 days of wellness"*).
   - Any errors (Garmin 429, missing wellness fields — name them concretely).
   - The new form numbers if PMC moved meaningfully (CTL Δ, TSB).
   - One-liner: *"Run /today for today's briefing."*

## Constraints

- Never re-pull data already cached (CLAUDE.md rule #6) — `sync_activities.py` dedupes via `UNIQUE(source, source_id)`.
- If `errors` includes a Garmin 429: mention it but don't retry-loop. Wait 30 min before next sync (`feedback_mcp_env_propagation.md`).
- If `synced.strava == 0` and `skipped.strava > 0`, that's normal — means everything is already cached.

# Tools catalog

Every tool here is a single-file Python script under `tools/`. Run with:

```
uv run python tools/<name>.py [args]
```

All tools follow the same contract:

- **stdout**: one JSON object.
- **stderr**: human-readable logs.
- exit 0 on success; non-zero with `{"error": "..."}` on stdout for failures.
- DB access via `tools/_common.py:open_db()`.
- Strava auth via `_common.strava_client()`; Garmin via `_common.garmin_client()`.
- Pure-function math (TSS, NP, PMC, fueling, wind/yaw, workouts) lives in `analysis/`.

When you (Claude) want a number, run the relevant tool. Don't try to guess from prior context.

---

## Auth & data ingest

### `auth_status.py`
Token + DB health for Strava + Garmin + Calendar. No args.

### `garmin_auth_setup.py`
Interactive Garmin SSO + MFA. Re-run on token expiry (~1 year).

### `sync_activities.py`
Pull Strava activities + (optionally) Garmin wellness into SQLite.
```
--since YYYY-MM-DD       default: 30 days ago
--limit N                cap on activities pulled
--include-streams        also pull power/HR streams; recompute TSS
--include-wellness       pull HRV/sleep/RHR/body battery/readiness
--no-strava / --no-garmin
```

### `list_activities.py`
Cache-only query.
```
--since {Nd | YYYY-MM-DD}     default 30 days ago
--sport {cycling|running|all} default all
--min-tss N
--limit N                     newest first
```

### `get_activity.py`
Full detail for one activity.
```
--id N                  required (DB row id)
--include-streams       attach decoded stream summaries
--include-stream-data   attach full numpy arrays as JSON (heavy)
```

### `estimate_ftp.py`
Propose an FTP from recent hard efforts.
```
--method {recent_np|best_20min}   default recent_np
--window-days N                   default 90
--commit                          persist to ftp_history
--note "..."
```

---

## Form & wellness

### `compute_pmc.py`
Recompute `pmc_daily` from activities.
```
--backfill            full rebuild
--recompute-days N    default 14
--through YYYY-MM-DD
```

### `current_form.py`
Today's CTL/ATL/TSB/ramp_7d/form_state. No args.

Output includes `ramp_warning` (>+8) and `ramp_critical` (>+10) flags plus `history_14d`.

### `daily_briefing.py`
Aggregates form, wellness, planned session, group rides, knee status into one JSON the `/today` skill renders.
```
--date YYYY-MM-DD   default today (Europe/Stockholm)
```

---

## Planning & workouts

### `generate_workout.py`
Pure-function workout structure.
```
--kind {endurance|recovery|sst|threshold|vo2|race}   required
--duration-min N                                     for endurance/recovery/race
--template STR                                       sst:{2x20|3x15|4x10}
                                                     threshold:{2x20|3x15|4x10|overunders}
                                                     vo2:{5x4|4x4_norwegian|6x3|30_15}
--name STR
```

### `export_workout.py`
Write `.zwo` (and optionally `.fit`).
```
--kind ... --duration-min N --template STR --name STR
--out PATH
--push-to-garmin    gated by TM_GARMIN_DRYRUN; .fit writing pending fit-tool integration
```

### `plan_week.py`
Propose a 7-day plan; write `journal/YYYY-WW-plan.md`.
```
--week-start YYYY-MM-DD              must be Monday; default next Monday
--mode {pyramidal|polarized|recovery|auto}   default auto (chooses from form_state)
--no-write                           print only, don't touch journal
```

---

## Calendar

### `calendar_list.py`
Read events from the Training Mate Google Calendar.
```
--from YYYY-MM-DD     default today
--to   YYYY-MM-DD     default from + 7 days
--calendar STR        override TM_CALENDAR_NAME
--json-only
```

### `calendar_upsert_week.py` *(planned)*
Diff a week's plan against existing calendar events; apply with confirmation. Not yet built — for now, use the `google-calendar` MCP server's create/update/delete-event tools after showing the diff.

---

## Segments / KOM / weather

### `sync_segments.py`
Pull Martin's starred Strava segments + precompute bearings.
```
--include-efforts
--limit N
```

### `route_weather.py`
Open-Meteo hourly forecast (no auth).
```
--lat FLOAT --lon FLOAT          single point
--polyline STR                   Strava precision-5 polyline
--hours-ahead N                  default 12
--sample-count N                 default 5 for polyline
```

### `kom_today.py`
Rank starred segments by best KOM-attack score over the next N hours.
```
--hours-ahead N         default 6
--top N                 default 5
--min-distance-m N      default 200
```

### `kom_threat.py`
Single-segment detail with full wind decomposition.
```
--segment-id N                 required
--hour-utc YYYY-MM-DDTHH:00    optional; default now
--user-power-w INT             optional; for realistic-threat scoring
```

---

## Fueling

### `fuel_plan.py`
Carbs / fluids / sodium plan for a ride.
```
--duration-h FLOAT       required
--IF FLOAT               required (intensity factor)
--temp-c FLOAT
--weight-kg FLOAT        override athlete_profile.weight_kg
--heavy-sweater
```

---

## Review & ops

### `weekly_review.py`
Diff plan vs actual for an ISO week.
```
--week YYYY-WW   default last completed week
```

Output includes `tss.{planned, actual}`, `form.{start, end, ctl_delta}`, per-day list, `session_distribution`.

### `rate_limits.py`
24-hour API usage from `rate_limit_log`.
```
--window-h N    default 24
```

---

## History & data hygiene

### `data_status.py`
Single-screen view of cache state + actionable gaps. The `/data-status` skill renders it for Martin.
```
--window-days N   for wellness coverage stats (default 90)
```

**Output:** `{schema_version, auth, activities: {count, oldest, newest, total_tss, by_source, top_sports, activities_with_streams}, pmc: {first_date, last_date, days_covered, current_ctl/atl/tsb, ramp_7d}, wellness: {window_days, days_with: {hrv, sleep, rhr, stress, ...}, gaps_in_window}, segments: {starred_count}, rate_limits: {...}, recommendations: [...]}`. The `recommendations` list is prioritized.

### `backfill.py`
Deep historical pull — Strava activities + Garmin wellness + segments + (optional) PMC recompute. Idempotent; safe to re-run.
```
--since YYYY-MM-DD       earliest date; default 2 years ago
--skip-strava            don't pull activities
--skip-wellness          don't pull Garmin wellness
--skip-segments          don't sync starred segments
--chunk-days N           wellness chunk size (default 30) — supports stop/resume
--recompute-pmc          run compute_pmc --backfill after activities land
--max-strava-pages N     cap Strava pages
```

Typical first-run pattern after auth bring-up:
```
uv run python tools/backfill.py --since 2024-01-01 --recompute-pmc
```

Strava backfill is fast (~1-2 min for 2 years). Garmin wellness is slow — chunked at 30 days × 0.7 s/day, so ~10 min for 6 months. The script can be killed and re-run; INSERT … ON CONFLICT keeps it idempotent.

---

## Operating notes for the agent

- **Always cite a doc** when giving training advice (CLAUDE.md rule #1). Tools return numbers; docs justify them.
- **Don't re-pull data** (rule #6). Check the SQLite cache first.
- **Strava 200/15min, 2000/day** (rule #7). `sync_activities.py` throttles, but watch `rate_limits.py` if doing heavy backfill.
- **Garmin MCP not autostarted** — for ad-hoc Garmin queries, run `npx -y @nicolasvegam/garmin-connect-mcp` manually, or use a `tools/*.py` query.
- **Calendar writes show a diff first** (rule #5). Until `calendar_upsert_week.py` lands, use the `google-calendar` MCP server with explicit confirmation.

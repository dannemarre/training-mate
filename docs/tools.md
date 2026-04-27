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
- Strava auth via `_common.strava_client()`; Garmin via `_common.garmin_client()` — both read the upstream MCP servers' on-disk caches.
- Pure-function math (TSS, NP, PMC, fueling, wind/yaw) lives in `analysis/`.

When you (Claude) want a number, run the relevant tool. Don't try to guess from prior context.

---

## `auth_status.py`

Report token + DB health for Strava + Garmin + Calendar. No args.

**Output (truncated):**
```json
{
  "strava": {"ok": true, "client_id": true, "access_token": true, "expires_at": ..., "expires_in_s": ..., "config_path": "..."},
  "garmin": {"ok": true, "format": "modern", "modern_present": true, "oauth1_present": false, "oauth2_present": false, "profile": null, "token_dir": "..."},
  "google_calendar": {"ok": true, "credentials_present": true, "token_files": ["gcp-oauth.keys.json", "tokens.json"], "calendar_name": "Training Mate"},
  "db": {"path": "...", "schema_version": 1}
}
```

---

## `garmin_auth_setup.py`

Interactive Garmin SSO + MFA. Reads `GARMIN_EMAIL` / `GARMIN_PASSWORD` from `.env`, prompts for MFA on stderr, saves tokens to `~/.garmin-mcp/garmin_tokens.json`. Re-run on token expiry (~1 year) or password change.

```
uv run python tools/garmin_auth_setup.py
```

**Output:** `{"ok": true, "token_dir": "...", "user": "...", "profile_id": ..., "format": "modern"}`

---

## `sync_activities.py`

Pull Strava activities + (optionally) Garmin wellness into SQLite. Strava is the primary activity source; Garmin is the wellness source.

```
--since YYYY-MM-DD       default: 30 days ago
--limit N                cap on activities pulled
--include-streams        also pull power/HR streams; recompute TSS
--include-wellness       pull HRV/sleep/RHR/body battery/readiness from Garmin
--no-strava              skip Strava sync
--no-garmin              skip Garmin (incl. wellness) sync
```

**Output:**
```json
{
  "synced": {"strava": 9, "garmin_wellness": 7},
  "skipped": {"strava": 0},
  "errors": [],
  "as_of_utc": "...",
  "profile_placeholders": ["ftp_w", ...]
}
```

The `profile_placeholders` field warns if FTP / LTHR / HR-anchors are still using defaults — fix via `tools/estimate_ftp.py --commit` or by editing `athlete_profile`.

---

## `list_activities.py`

Query the cached activities table. No API calls.

```
--since {Nd | YYYY-MM-DD}   default: 30 days ago
--sport {cycling|running|all}  default: all
--min-tss N                 filter
--limit N                   cap, newest first
```

**Output:** `{"count": N, "since": "...", "activities": [{...}]}` — each activity has the human-relevant subset (id, sport, start_utc, duration_s/min, distance_m/km, avg_power, np, intensity_factor, tss, tss_kind, kj, avg_hr, max_hr, elevation_gain_m, np_low_confidence).

---

## `get_activity.py`

Full detail for one activity. `--id` is the DB row id (use `list_activities.py` to find it).

```
--id N                   required
--include-streams        attach decoded stream summaries (length, mean, max, min)
--include-stream-data    attach the full numpy arrays as JSON (heavy)
```

**Output:** `{"activity": {...}, "streams": {"power": {...}, "hr": {...}}}`

---

## `estimate_ftp.py`

Propose an FTP from recent hard efforts.

```
--method {recent_np|best_20min}   default: recent_np
--window-days N                   default: 90
--commit                          persist to ftp_history (otherwise dry-run)
--note "..."                      annotation for the ftp_history row
```

**Output:**
```json
{
  "method": "recent_np",
  "current_ftp": 240,
  "proposed_ftp": 268,
  "evidence": [{"activity_id": ..., "duration_min": 22.5, "np": 282.0, "tss": 79}],
  "rationale": "0.95 × highest qualifying NP in window",
  "committed": false,
  "effective_date": null,
  "window_days": 90
}
```

`recent_np` = take highest 20+ min effort by NP, multiply by 0.95.
`best_20min` = same, but only proposes a change if NP exceeds 105% of current FTP.

---

## Google Calendar — for now, use the upstream MCP server directly

Until `tools/calendar_*.py` land in M5, calendar reads/writes go through the `google-calendar` MCP server (`@cocal/google-calendar-mcp`) autostarted via `.mcp.json`. Always:

- Restrict to the `Training Mate` calendar (configured via `TM_CALENDAR_NAME` in `.env`).
- Show a diff before writing — list each create / update / delete, wait for explicit approval.
- Update the corresponding `journal/YYYY-WW-plan.md`'s "Calendar" section after a successful push.

---

## Garmin MCP — manual ad-hoc only

The Garmin MCP server (`@nicolasvegam/garmin-connect-mcp`) is **not autostarted** (see `BUILDOUT.md` — empty-env retry-loops trigger SSO 429s, and garth is deprecated). Either:

- Use a `tools/*.py` query (post-M2 these exist: `list_activities.py`, `get_activity.py`, `daily_briefing.py`).
- Or invoke `npx -y @nicolasvegam/garmin-connect-mcp` manually for one-off natural-language Garmin queries.

---

## `compute_pmc.py`

Recompute `pmc_daily` from activities.

```
--backfill            full rebuild from earliest activity (or 365d ago)
--recompute-days N    default 14 (always at least 14, to cover edits)
--through YYYY-MM-DD  end date; default today (Europe/Stockholm)
```

**Output:** `{"computed_through": ..., "rows_written": N, "first_date": ..., "ctl": ..., "atl": ..., "tsb": ..., "form_state": "...", "seed_ctl": ..., "seed_atl": ..., "seed_date": ...}`

Run `--backfill` once after a fresh sync; thereafter the incremental mode is enough.

---

## `current_form.py`

Today's form state. Read-only against `pmc_daily`.

**Output:**
```json
{
  "as_of": "2026-04-27", "ctl": 47.0, "atl": 89.6, "tsb": -56.4,
  "ramp_7d": 4.25, "form_state": "risky",
  "ramp_warning": false, "ramp_critical": false,
  "citation": "docs/training-science.md#tsb-interpretation-thresholds",
  "history_14d": [{"date": ..., "tss": ..., "ctl": ..., "atl": ..., "tsb": ...}]
}
```

`form_state` is one of: `crashing`, `risky`, `overreached`, `productive`, `neutral`, `race-ready`, `detrained`. See `docs/training-science.md#form-state-buckets`.

---

## `daily_briefing.py`

Aggregate today's signals (form + wellness + plan + group rides + knee). The `/today` skill consumes this.

```
--date YYYY-MM-DD   default: today (Europe/Stockholm)
```

**Output:** `{date, weekday, form, wellness, today_session, group_rides, knee_alert, knee_recent, advisory: [...]}`. The `advisory` array is the prioritized list of headline signals (ramp warnings, HRV breaches, sleep deficits, knee status) the agent should surface first.

---

## Planned (M5+)
- `generate_workout.py --type sst|vo2|threshold|endurance|recovery --duration <min>` — structured workout JSON.
- `export_workout.py --in workout.json --format zwo|fit` — emit `.zwo` (always) and optionally `.fit` (with `--push-to-garmin`).
- `plan_week.py --start YYYY-MM-DD` — 7-day skeleton respecting current form.
- `sync_segments.py` — pull starred Strava segments + precompute bearings.
- `route_weather.py --route_id <int>` — Open-Meteo hour-by-hour along a route.
- `kom_today.py [--lat --lon --radius_km]` — wind-ranked starred segments.
- `kom_threat.py --segment_id <int>` — can-I-take-it scoring.
- `fuel_plan.py --duration_h --IF --temp_c` — carbs/fluids/sodium plan.
- `weekly_review.py` — last 7 days vs plan, lessons.
- `calendar_list.py --from --to` — events in window.
- `calendar_upsert_week.py --plan journal/YYYY-WW-plan.md [--apply]` — diff/apply.
- `rate_limits.py` — 24h API usage by provider.

Each will be added here with full args + example JSON when implemented.

# Tools catalog

Every tool here is a single-file Python script under `tools/`. Run with:

```
uv run python tools/<name>.py [args]
```

All tools follow the same contract:

- stdout: one JSON object.
- stderr: human-readable logs.
- exit 0 on success; non-zero with `{"error": "..."}` on stdout for failures.
- DB access goes through `tools/_common.py:open_db()`.
- Strava/Garmin auth goes through `_common.strava_client()` / `garmin_client()`, which read the upstream MCP servers' on-disk caches.

When you (Claude) want a number, run the relevant tool. Don't try to guess from prior context.

---

## `auth_status.py`

Report token + DB health for all three integrations. No args.

**Example output:**
```json
{
  "strava": {"ok": true, "client_id": true, "access_token": true,
             "expires_at": 1745000000, "expires_in_s": 3000,
             "config_path": "/root/.config/strava-mcp/config.json"},
  "garmin": {"ok": true, "oauth1_present": true, "oauth2_present": true,
             "profile": {"displayName": "athlete", "profileId": 12345},
             "token_dir": "/root/.garmin-mcp"},
  "google_calendar": {"ok": true, "credentials_path": "/path/to/gcp-oauth.keys.json",
                      "credentials_present": true,
                      "token_dir": "/root/.config/google-calendar-mcp",
                      "token_files": ["tokens.json"],
                      "calendar_name": "Training"},
  "db":     {"path": "/home/user/training-mate/data/training-mate.sqlite",
             "existed_before": true, "schema_version": 1}
}
```

Use this whenever a sync or calendar tool errors with auth-related messages. `google_calendar.ok = false` while `credentials_present = true` means the upstream MCP server needs to be invoked once interactively to complete the OAuth browser flow.

---

## Google Calendar — for now, use the upstream MCP server directly

Until `tools/calendar_*.py` land in M5, calendar reads/writes go through the `google-calendar` MCP server (`@cocal/google-calendar-mcp`). Its tools (`list-events`, `create-event`, `update-event`, `delete-event`) are available in any Claude Code session that has `.mcp.json` loaded. Always:

- Restrict to the `Training` calendar (configured via `TM_CALENDAR_NAME` in `.env`).
- Show a diff before writing — list each create / update / delete, wait for explicit approval.
- Update the corresponding `journal/YYYY-WW-plan.md`'s "Calendar" section after a successful push.

## (planned, M2+)

- `sync_activities.py --since <30d|YYYY-MM-DD>` — Strava + Garmin → `activities` + `activity_streams`.
- `list_activities.py --since --sport --limit` — query the cache.
- `get_activity.py --id <int>` — full activity + stream summary.
- `compute_pmc.py [--days N]` — recompute `pmc_daily` for last N days (default 14).
- `current_form.py` — CTL/ATL/TSB today + 7-day delta.
- `estimate_ftp.py` — from 20-min/8-min efforts in last 90 days.
- `generate_workout.py --type sst|vo2|threshold|endurance|recovery --duration <min>`.
- `export_workout.py --in workout.json --format zwo|erg|mrc`.
- `plan_week.py --start YYYY-MM-DD` — 7-day skeleton respecting current TSB.
- `sync_segments.py` — pull starred segments + precompute bearings.
- `kom_today.py --lat --lon --radius_km` — wind-ranked segments for today.
- `kom_threat.py --segment_id <int>` — can-I-take-it score.
- `route_weather.py --route_id <int>` — hour-by-hour weather along the route.
- `fuel_plan.py --duration_h --IF --temp_c` — carbs/fluids/sodium plan.
- `daily_briefing.py` — aggregate form + plan + weather + fueling.
- `weekly_review.py` — last 7 days vs plan.
- `calendar_list.py --from --to` — events in window from the Training calendar.
- `calendar_upsert_week.py --plan journal/YYYY-WW-plan.md [--apply]` — diff (default) or apply, against the Training calendar.

Each will be added here with its full arg list and example JSON when implemented.

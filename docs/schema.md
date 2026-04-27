# SQLite schema

DB path: `data/training-mate.sqlite` (WAL mode). Created and migrated automatically on first tool run via `tools/_common.py:open_db()`. Schema version stored in `PRAGMA user_version`.

## Tables

### `athlete_profile`

Single-row table (`id = 1`). FTP/HR/weight defaults read from here when a tool needs them.

```sql
id, name, weight_kg, ftp_w, lthr, max_hr, rhr,
run_threshold_pace_s_per_km, sex, timezone, updated_at
```

### `ftp_history`

Append-only log of FTP changes. PK is `effective_date`. PMC tools that recompute history use the FTP active on each activity's date, not the current FTP.

### `activities`

```sql
id, source ('strava'|'garmin'), source_id,
sport, start_utc, duration_s, distance_m,
avg_power, np, intensity_factor, tss, tss_kind ('power'|'hr'|'pace'),
kj, avg_hr, max_hr, elevation_gain_m, polyline,
raw (json from source), np_low_confidence, created_at
UNIQUE (source, source_id)
```

### `activity_streams`

Per-activity numeric streams. `blob` is zstd-compressed numpy bytes; the kind is one of `power | hr | cadence | speed | altitude | latlng | time | grade`.

### `wellness_daily`

Garmin-derived: HRV, body battery, readiness, sleep, RHR. Keyed by local date.

### `pmc_daily`

```sql
date (local YYYY-MM-DD, PK), tss, ctl, atl, tsb
```

Recomputed by `tools/compute_pmc.py`.

### `segments` / `segment_efforts`

Starred Strava segments + your efforts on them. `bearing_deg` is precomputed start→end bearing so KOM tools don't recompute it on every wind query.

### `routes`, `plans`, `workouts`

Planning state. `workouts.structure_json` holds the interval structure used by `export_workout.py` to emit `.zwo` / `.erg` / `.mrc`.

### `weather_forecast`

Open-Meteo cache, keyed by `(lat, lon, hour_utc)`.

### `rate_limit_log`

Strava + Garmin rate-limit usage from response headers. Used by sync tools to back off.

## Example queries

**Last 14 days of TSS:**
```sql
SELECT date, tss, ctl, atl, tsb
FROM pmc_daily
WHERE date >= date('now','-14 days')
ORDER BY date;
```

**This week's activities:**
```sql
SELECT start_utc, sport, duration_s/60 AS min, tss, np, intensity_factor
FROM activities
WHERE start_utc >= datetime('now','-7 days')
ORDER BY start_utc DESC;
```

**Starred segments not yet attempted:**
```sql
SELECT s.id, s.name, s.distance_m, s.avg_grade
FROM segments s
LEFT JOIN segment_efforts e ON e.segment_id = s.id
WHERE s.starred = 1 AND e.id IS NULL;
```

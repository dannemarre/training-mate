"""sync_activities — pull Strava activities + Garmin wellness into SQLite.

Args:
    --since YYYY-MM-DD   default: 30 days ago (or last sync watermark)
    --limit N            optional cap on activities pulled (Strava only)
    --include-streams    also pull power/HR streams; recompute TSS from them
    --include-wellness   pull Garmin daily wellness (HRV, sleep, RHR, body battery, readiness)
    --no-strava          skip the Strava activity sync
    --no-garmin          skip the Garmin sync (activities + wellness)

Output:
    {
      "synced": {"strava": N, "garmin_wellness": N},
      "skipped": {"strava": N},
      "errors": [...],
      "rate_limit": {...},
      "as_of_utc": "..."
    }

Strategy:
- **Strava is the primary activity source.** Garmin-recorded rides sync
  through Garmin → Strava already; pulling them twice would dedupe poorly.
- **Garmin is the wellness source** — HRV, sleep, RHR, body battery,
  training readiness — fields Strava does not expose.
- Streams are opt-in (heavy). When `--include-streams` is set, fetch
  watts + heartrate streams and recompute TSS from them (more accurate
  than Strava's `weighted_average_watts`).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from typing import Any

import numpy as np
from _common import (  # type: ignore[import-not-found]
    athlete_profile,
    emit,
    encode_stream,
    fail,
    ftp_at,
    log,
    open_db,
)

import analysis.tss as tss


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--since", help="YYYY-MM-DD; default 30d ago")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--include-streams", action="store_true")
    p.add_argument("--include-wellness", action="store_true")
    p.add_argument("--no-strava", action="store_true")
    p.add_argument("--no-garmin", action="store_true")
    return p.parse_args(argv)


def _since_default() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)


# ---------------------------------------------------------------------------
# Strava
# ---------------------------------------------------------------------------


def _activity_to_row(act: Any, profile: dict, recomputed: dict | None) -> dict:
    """Map a stravalib SummaryActivity (+ optionally recomputed TSS) → DB row."""
    start_utc = act.start_date  # datetime, UTC per stravalib
    if isinstance(start_utc, dt.datetime):
        start_utc_str = start_utc.astimezone(dt.timezone.utc).isoformat()
        date_iso = start_utc.astimezone(dt.timezone.utc).date().isoformat()
    else:
        start_utc_str = str(start_utc)
        date_iso = dt.date.today().isoformat()

    duration_s = int(getattr(act, "moving_time", 0) or 0)
    if isinstance(getattr(act, "moving_time", None), dt.timedelta):
        duration_s = int(act.moving_time.total_seconds())

    distance_m = float(getattr(act, "distance", 0) or 0.0)
    avg_power = getattr(act, "average_watts", None)
    np_summary = getattr(act, "weighted_average_watts", None)
    avg_hr = getattr(act, "average_heartrate", None)
    max_hr = getattr(act, "max_heartrate", None)
    kj = getattr(act, "kilojoules", None)
    elev = getattr(act, "total_elevation_gain", None)
    polyline = None
    if getattr(act, "map", None) and getattr(act.map, "summary_polyline", None):
        polyline = act.map.summary_polyline

    raw_sport = (
        getattr(act, "sport_type", None)
        or getattr(act, "type", None)
        or "Other"
    )
    # stravalib v2 wraps activity type in a Pydantic RootModel — unwrap
    if hasattr(raw_sport, "root"):
        raw_sport = raw_sport.root
    sport = str(raw_sport).lower()

    # TSS computation priority: recomputed-from-streams > from-summary-NP > hrTSS-fallback
    tss_value: float | None = None
    tss_kind: str | None = None
    if_value: float | None = None
    np_low_conf = False

    if recomputed is not None and recomputed.get("tss") is not None:
        tss_value = recomputed["tss"]
        tss_kind = "power"
        if_value = recomputed.get("intensity_factor")
        np_summary = recomputed.get("np", np_summary)
        kj = recomputed.get("kj", kj)
        np_low_conf = recomputed.get("np_low_confidence", False) or recomputed.get("np_unreliable", False)
    elif np_summary and duration_s > 0:
        # Use Strava's weighted_average_watts as NP, with FTP active on this date
        ftp = ftp_at(date_iso)
        if_value = np_summary / ftp
        tss_value = (duration_s / 3600) * if_value**2 * 100
        tss_kind = "power"
        np_low_conf = duration_s < tss.NP_LOW_CONF_MAX
    elif avg_hr and duration_s > 0:
        # Fallback hrTSS using LTHR
        prof_lthr = profile["lthr"]
        result = tss.hr_tss_avg(avg_hr=float(avg_hr), duration_s=duration_s, lthr=prof_lthr)
        tss_value = result["tss"]
        tss_kind = "hr"

    return {
        "source": "strava",
        "source_id": str(act.id),
        "sport": sport,
        "start_utc": start_utc_str,
        "duration_s": duration_s,
        "distance_m": distance_m if distance_m > 0 else None,
        "avg_power": float(avg_power) if avg_power is not None else None,
        "np": float(np_summary) if np_summary is not None else None,
        "intensity_factor": float(if_value) if if_value is not None else None,
        "tss": float(tss_value) if tss_value is not None else None,
        "tss_kind": tss_kind,
        "kj": float(kj) if kj is not None else None,
        "avg_hr": float(avg_hr) if avg_hr is not None else None,
        "max_hr": float(max_hr) if max_hr is not None else None,
        "elevation_gain_m": float(elev) if elev is not None else None,
        "polyline": polyline,
        "np_low_confidence": 1 if np_low_conf else 0,
    }


def _fetch_streams_recompute(
    client: Any, activity_id: int, profile: dict, date_iso: str, conn: Any
) -> dict | None:
    """Pull watts + heartrate streams, persist them, recompute TSS."""
    try:
        streams = client.get_activity_streams(
            activity_id, types=["watts", "heartrate", "time"], resolution="high"
        )
    except Exception as e:  # noqa: BLE001
        log(f"  [strava] streams failed for {activity_id}: {e}")
        return None
    if not streams:
        return None

    out: dict[str, Any] = {}
    if "watts" in streams and streams["watts"].data:
        watts = np.asarray(streams["watts"].data, dtype=float)
        ftp = ftp_at(date_iso)
        result = tss.power_tss(watts, ftp=ftp, sample_hz=1.0)
        out.update(result)
        # persist stream
        conn.execute(
            "INSERT OR REPLACE INTO activity_streams (activity_id, kind, sample_hz, blob) "
            "VALUES (?, 'power', 1.0, ?)",
            (activity_id, encode_stream(watts)),
        )
    if "heartrate" in streams and streams["heartrate"].data:
        hr = np.asarray(streams["heartrate"].data, dtype=float)
        conn.execute(
            "INSERT OR REPLACE INTO activity_streams (activity_id, kind, sample_hz, blob) "
            "VALUES (?, 'hr', 1.0, ?)",
            (activity_id, encode_stream(hr)),
        )
    return out if out else None


def _sync_strava(
    args: argparse.Namespace, since: dt.datetime, profile: dict, conn: Any
) -> dict[str, Any]:
    from _common import strava_client  # type: ignore[import-not-found]

    log(f"[strava] sync from {since.isoformat()}")
    client, _tokens = strava_client()
    synced = 0
    skipped = 0
    errors: list[dict] = []
    last_act_at: str | None = None

    cur = conn.cursor()
    iterator = client.get_activities(after=since, limit=args.limit)
    for i, act in enumerate(iterator):
        if args.limit is not None and i >= args.limit:
            break
        try:
            existing = cur.execute(
                "SELECT id FROM activities WHERE source = 'strava' AND source_id = ?",
                (str(act.id),),
            ).fetchone()
            if existing is not None:
                skipped += 1
                continue

            recomputed = None
            if args.include_streams:
                date_iso = (
                    act.start_date.astimezone(dt.timezone.utc).date().isoformat()
                    if isinstance(act.start_date, dt.datetime)
                    else dt.date.today().isoformat()
                )
                recomputed = _fetch_streams_recompute(client, act.id, profile, date_iso, cur)
                # Mild throttle to stay well under 200/15min when streams are on
                time.sleep(0.5)

            row = _activity_to_row(act, profile, recomputed)
            cur.execute(
                """
                INSERT INTO activities (
                  source, source_id, sport, start_utc, duration_s, distance_m,
                  avg_power, np, intensity_factor, tss, tss_kind, kj,
                  avg_hr, max_hr, elevation_gain_m, polyline,
                  np_low_confidence, created_at
                ) VALUES (
                  :source, :source_id, :sport, :start_utc, :duration_s, :distance_m,
                  :avg_power, :np, :intensity_factor, :tss, :tss_kind, :kj,
                  :avg_hr, :max_hr, :elevation_gain_m, :polyline,
                  :np_low_confidence, datetime('now')
                )
                """,
                row,
            )
            synced += 1
            last_act_at = row["start_utc"]
        except Exception as e:  # noqa: BLE001
            errors.append({"activity_id": getattr(act, "id", None), "error": str(e)})
            log(f"  [strava] failed: {e}")

    return {"synced": synced, "skipped": skipped, "errors": errors, "last_act_at": last_act_at}


# ---------------------------------------------------------------------------
# Garmin wellness
# ---------------------------------------------------------------------------


def _sync_garmin_wellness(since: dt.date, conn: Any) -> dict[str, Any]:
    from _common import garmin_client  # type: ignore[import-not-found]

    log(f"[garmin/wellness] sync from {since.isoformat()}")
    try:
        client = garmin_client()
    except Exception as e:  # noqa: BLE001
        return {"synced": 0, "errors": [{"step": "login", "error": str(e)}]}

    synced = 0
    errors: list[dict] = []
    today = dt.date.today()
    d = since
    while d <= today:
        date_str = d.isoformat()
        try:
            row = _fetch_one_day_wellness(client, date_str)
            conn.execute(
                """
                INSERT INTO wellness_daily (
                  date, hrv_ms, body_battery, readiness, sleep_score,
                  sleep_minutes, resting_hr, raw
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                  hrv_ms        = excluded.hrv_ms,
                  body_battery  = excluded.body_battery,
                  readiness     = excluded.readiness,
                  sleep_score   = excluded.sleep_score,
                  sleep_minutes = excluded.sleep_minutes,
                  resting_hr    = excluded.resting_hr,
                  raw           = excluded.raw
                """,
                (
                    date_str,
                    row.get("hrv_ms"),
                    row.get("body_battery"),
                    row.get("readiness"),
                    row.get("sleep_score"),
                    row.get("sleep_minutes"),
                    row.get("resting_hr"),
                    json.dumps(row.get("raw", {}), default=str),
                ),
            )
            synced += 1
        except Exception as e:  # noqa: BLE001
            errors.append({"date": date_str, "error": str(e)})
            log(f"  [garmin/wellness] {date_str} failed: {e}")
        # Garmin rate limit: ≤1 req/s. Be polite.
        time.sleep(0.7)
        d += dt.timedelta(days=1)

    return {"synced": synced, "errors": errors}


def _fetch_one_day_wellness(client: Any, date_str: str) -> dict[str, Any]:
    """Best-effort wellness pull. Each metric in its own try so a single
    failure doesn't lose the day."""
    out: dict[str, Any] = {"raw": {}}

    # HRV (overnight rMSSD). Method may be `get_hrv_data` on python-garminconnect.
    try:
        hrv_doc = client.get_hrv_data(date_str)
        out["raw"]["hrv"] = hrv_doc
        if isinstance(hrv_doc, dict):
            summary = hrv_doc.get("hrvSummary") or {}
            out["hrv_ms"] = summary.get("lastNightAvg") or summary.get("weeklyAvg")
    except Exception as e:  # noqa: BLE001
        out["raw"]["hrv_error"] = str(e)

    # Body battery
    try:
        bb = client.get_body_battery(date_str)
        out["raw"]["body_battery"] = bb
        if isinstance(bb, list) and bb:
            # Garmin returns a per-day list; pick the day's max body battery
            charged = bb[0].get("charged") if isinstance(bb[0], dict) else None
            out["body_battery"] = charged
    except Exception as e:  # noqa: BLE001
        out["raw"]["body_battery_error"] = str(e)

    # Sleep
    try:
        sleep_doc = client.get_sleep_data(date_str)
        out["raw"]["sleep"] = sleep_doc
        if isinstance(sleep_doc, dict):
            dto = sleep_doc.get("dailySleepDTO") or {}
            sleep_seconds = dto.get("sleepTimeSeconds")
            if sleep_seconds:
                out["sleep_minutes"] = int(sleep_seconds // 60)
            score = dto.get("sleepScores", {}).get("overallScore", {})
            if isinstance(score, dict):
                out["sleep_score"] = score.get("value")
    except Exception as e:  # noqa: BLE001
        out["raw"]["sleep_error"] = str(e)

    # Resting heart rate
    try:
        summary = client.get_user_summary(date_str)
        out["raw"]["user_summary"] = summary
        if isinstance(summary, dict):
            out["resting_hr"] = summary.get("restingHeartRate")
    except Exception as e:  # noqa: BLE001
        out["raw"]["user_summary_error"] = str(e)

    # Training readiness
    try:
        readiness = client.get_training_readiness(date_str)
        out["raw"]["readiness"] = readiness
        if isinstance(readiness, list) and readiness:
            out["readiness"] = readiness[0].get("score") if isinstance(readiness[0], dict) else None
    except Exception as e:  # noqa: BLE001
        out["raw"]["readiness_error"] = str(e)

    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str]) -> None:
    args = _parse_args(argv)

    if args.since:
        since_dt = dt.datetime.fromisoformat(args.since).replace(tzinfo=dt.timezone.utc)
    else:
        since_dt = _since_default()
    since_date = since_dt.date()

    profile = athlete_profile()
    if profile.get("placeholders_used"):
        log(f"[profile] placeholders in use for: {profile['placeholders_used']}")

    out: dict[str, Any] = {
        "synced": {"strava": 0, "garmin_wellness": 0},
        "skipped": {"strava": 0},
        "errors": [],
        "as_of_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "profile_placeholders": profile.get("placeholders_used", []),
    }

    with open_db() as conn:
        if not args.no_strava:
            try:
                r = _sync_strava(args, since_dt, profile, conn)
                out["synced"]["strava"] = r["synced"]
                out["skipped"]["strava"] = r["skipped"]
                out["errors"].extend(r["errors"])
            except Exception as e:  # noqa: BLE001
                out["errors"].append({"step": "strava", "error": str(e)})

        if args.include_wellness and not args.no_garmin:
            try:
                w = _sync_garmin_wellness(since_date, conn)
                out["synced"]["garmin_wellness"] = w["synced"]
                out["errors"].extend(w["errors"])
            except Exception as e:  # noqa: BLE001
                out["errors"].append({"step": "garmin_wellness", "error": str(e)})

    emit(out)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        fail("interrupted", code=130)

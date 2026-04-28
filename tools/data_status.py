"""data_status — single-screen view of what's in the local cache and what's missing.

Args:
    --window-days N   for wellness coverage stats (default 90)

Output:
    {
      "as_of": "...",
      "schema_version": 2,
      "auth": {strava, garmin, calendar booleans},
      "activities": {count, oldest, newest, gap_days, total_tss, by_source, by_sport_top, last_synced_streams_for: id|null},
      "pmc": {first_date, last_date, days_covered, current_ctl, atl, tsb, ramp_7d},
      "wellness": {window_days, days_with: {sleep, rhr, stress, hrv, body_battery, readiness}, gaps: int, latest_date},
      "segments": {starred_count, last_synced},
      "rate_limits": {... per-provider snapshot ...},
      "recommendations": [list of "do X" strings]
    }

Designed so the agent can run this once at session start and reason
about data quality before making coaching calls. The /data-status skill
formats it for Martin.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys

from _common import emit, fail, open_db  # type: ignore[import-not-found]


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--window-days", type=int, default=90)
    return p.parse_args(argv)


def _auth_block() -> dict:
    """Light auth check without re-running auth_status (avoid duplicate import)."""
    from pathlib import Path

    home = Path.home()
    return {
        "strava": (home / ".config/strava-mcp/config.json").exists(),
        "garmin": (home / ".garmin-mcp/garmin_tokens.json").exists()
        or ((home / ".garmin-mcp/oauth1_token.json").exists() and (home / ".garmin-mcp/oauth2_token.json").exists()),
        "calendar": (home / ".config/google-calendar-mcp/tokens.json").exists(),
    }


def _activities_block(conn) -> dict:
    n = conn.execute("SELECT COUNT(*) AS n FROM activities").fetchone()["n"]
    if n == 0:
        return {"count": 0}
    bounds = conn.execute(
        "SELECT MIN(start_utc) AS a, MAX(start_utc) AS b, SUM(tss) AS s FROM activities"
    ).fetchone()
    by_source = {
        r["source"]: r["n"]
        for r in conn.execute(
            "SELECT source, COUNT(*) AS n FROM activities GROUP BY source"
        )
    }
    by_sport = [
        {"sport": r["sport"], "n": r["n"]}
        for r in conn.execute(
            "SELECT sport, COUNT(*) AS n FROM activities GROUP BY sport ORDER BY n DESC LIMIT 5"
        )
    ]
    streamed = conn.execute(
        "SELECT COUNT(DISTINCT activity_id) AS n FROM activity_streams"
    ).fetchone()["n"]
    return {
        "count": n,
        "oldest": bounds["a"],
        "newest": bounds["b"],
        "total_tss": round(float(bounds["s"] or 0), 1),
        "by_source": by_source,
        "top_sports": by_sport,
        "activities_with_streams": streamed,
    }


def _pmc_block(conn) -> dict:
    bounds = conn.execute(
        "SELECT MIN(date) AS a, MAX(date) AS b, COUNT(*) AS n FROM pmc_daily"
    ).fetchone()
    if not bounds or bounds["n"] == 0:
        return {"days_covered": 0}
    last = conn.execute(
        "SELECT date, ctl, atl, tsb FROM pmc_daily ORDER BY date DESC LIMIT 1"
    ).fetchone()
    seven_back = (dt.date.fromisoformat(last["date"]) - dt.timedelta(days=7)).isoformat()
    earlier = conn.execute(
        "SELECT ctl FROM pmc_daily WHERE date <= ? ORDER BY date DESC LIMIT 1",
        (seven_back,),
    ).fetchone()
    ramp = (
        round(float(last["ctl"]) - float(earlier["ctl"]), 2)
        if earlier
        else None
    )
    return {
        "first_date": bounds["a"],
        "last_date": bounds["b"],
        "days_covered": bounds["n"],
        "current_ctl": round(float(last["ctl"]), 2),
        "current_atl": round(float(last["atl"]), 2),
        "current_tsb": round(float(last["tsb"]), 2),
        "ramp_7d": ramp,
    }


def _wellness_block(conn, window_days: int) -> dict:
    cutoff = (dt.date.today() - dt.timedelta(days=window_days)).isoformat()
    rows = conn.execute(
        "SELECT date, hrv_ms, body_battery, readiness, sleep_minutes, resting_hr, "
        "stress_avg, avg_waking_respiration "
        "FROM wellness_daily WHERE date >= ? ORDER BY date",
        (cutoff,),
    ).fetchall()
    if not rows:
        return {"window_days": window_days, "days_with": {}, "latest_date": None, "gaps": window_days}

    days_with = {
        "hrv": sum(1 for r in rows if r["hrv_ms"] is not None),
        "body_battery": sum(1 for r in rows if r["body_battery"] is not None),
        "readiness": sum(1 for r in rows if r["readiness"] is not None),
        "sleep": sum(1 for r in rows if r["sleep_minutes"] is not None),
        "rhr": sum(1 for r in rows if r["resting_hr"] is not None),
        "stress": sum(1 for r in rows if r["stress_avg"] is not None),
        "respiration": sum(1 for r in rows if r["avg_waking_respiration"] is not None),
    }

    # gaps = days in window with no row at all
    seen_dates = {r["date"] for r in rows}
    expected = set()
    d = dt.date.fromisoformat(cutoff)
    today = dt.date.today()
    while d <= today:
        expected.add(d.isoformat())
        d += dt.timedelta(days=1)
    gaps = len(expected - seen_dates)

    return {
        "window_days": window_days,
        "rows_in_window": len(rows),
        "days_with": days_with,
        "gaps_in_window": gaps,
        "latest_date": rows[-1]["date"] if rows else None,
    }


def _segments_block(conn) -> dict:
    n = conn.execute("SELECT COUNT(*) AS n FROM segments WHERE starred = 1").fetchone()["n"]
    return {"starred_count": n}


def _rate_limits_block(conn) -> dict:
    rows = conn.execute(
        "SELECT provider, COUNT(*) AS n, MAX(ts_utc) AS last "
        "FROM rate_limit_log WHERE ts_utc >= datetime('now', '-1 day') "
        "GROUP BY provider"
    ).fetchall()
    return {r["provider"]: {"requests_24h": r["n"], "last_seen": r["last"]} for r in rows}


def _recommendations(activities: dict, pmc: dict, wellness: dict, segments: dict) -> list[str]:
    recs = []
    today = dt.date.today()

    if activities.get("count", 0) == 0:
        recs.append("No activities cached. Run `tools/backfill.py --since 2024-01-01` to pull history.")
    else:
        oldest = dt.datetime.fromisoformat(activities["oldest"].replace("Z", "+00:00")).date()
        days = (today - oldest).days
        if days < 60:
            recs.append(
                f"Only {days} days of history. CTL is bootstrap-low — pull at least 6 months "
                f"(`tools/backfill.py --since {(today - dt.timedelta(days=180)).isoformat()}`)."
            )
        newest = dt.datetime.fromisoformat(activities["newest"].replace("Z", "+00:00")).date()
        if (today - newest).days >= 2:
            recs.append(
                f"Newest activity is {newest.isoformat()} ({(today - newest).days}d old). Run `/sync` to refresh."
            )
        if activities.get("activities_with_streams", 0) == 0 and activities["count"] > 0:
            recs.append(
                "No power/HR streams cached. Run `sync_activities.py --include-streams --since YYYY-MM-DD` "
                "for activities you want detailed analysis on."
            )

    if pmc.get("days_covered", 0) < 60 and activities.get("count", 0) > 0:
        recs.append(
            "PMC has fewer than 60 days. Run `tools/compute_pmc.py --backfill` after the activity backfill lands."
        )

    if wellness.get("days_with", {}).get("hrv", 0) == 0 and wellness.get("rows_in_window", 0) > 0:
        recs.append(
            "HRV unavailable on this Garmin (likely watch model). Wellness gating uses sleep + RHR drift + "
            "stress (per docs/wellness.md). No action needed."
        )
    if wellness.get("gaps_in_window", 0) > 0:
        recs.append(
            f"{wellness['gaps_in_window']} day gaps in wellness over the last {wellness['window_days']}d. "
            f"Run `sync_activities.py --include-wellness --since {(today - dt.timedelta(days=wellness['window_days'])).isoformat()}` to fill."
        )

    if segments.get("starred_count", 0) == 0:
        recs.append(
            "No starred segments cached. Run `tools/sync_segments.py` for /kom support."
        )

    if not recs:
        recs.append("Data looks healthy. /sync, /today, /plan-week are all good to go.")
    return recs


def main(argv: list[str]) -> None:
    args = _parse_args(argv)
    with open_db() as conn:
        activities = _activities_block(conn)
        pmc = _pmc_block(conn)
        wellness = _wellness_block(conn, args.window_days)
        segments = _segments_block(conn)
        rate_limits = _rate_limits_block(conn)
        sv_row = conn.execute("PRAGMA user_version").fetchone()
        schema_v = int(sv_row[0])

    out = {
        "as_of": dt.datetime.now(dt.timezone.utc).isoformat(),
        "schema_version": schema_v,
        "auth": _auth_block(),
        "activities": activities,
        "pmc": pmc,
        "wellness": wellness,
        "segments": segments,
        "rate_limits": rate_limits,
        "recommendations": _recommendations(activities, pmc, wellness, segments),
    }
    emit(out)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception as e:  # noqa: BLE001
        fail(str(e))

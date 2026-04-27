"""list_activities — query the local activities cache.

Args:
    --since N or YYYY-MM-DD   default: 30 days ago. "7d" / "14d" shortcuts work.
    --sport {cycling,running,all}  default: all
    --min-tss N               default: no filter
    --limit N                 default: no limit; orders newest first

Output:
    JSON array of activity rows with the human-relevant subset of columns.
    No streams. (Use get_activity.py for full detail.)
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from typing import Any

from _common import emit, open_db  # type: ignore[import-not-found]

CYCLING_SPORTS = {"ride", "virtualride", "ebikeride", "cycling", "gravelride", "mountainbikeride"}
RUNNING_SPORTS = {"run", "trailrun", "virtualrun", "running"}


def _parse_since(s: str | None) -> str:
    if not s:
        return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)).isoformat()
    m = re.fullmatch(r"(\d+)\s*d", s.strip(), flags=re.I)
    if m:
        days = int(m.group(1))
        return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)).isoformat()
    return dt.datetime.fromisoformat(s).isoformat()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--since", help="N days ago (e.g. '14d') or YYYY-MM-DD")
    p.add_argument("--sport", choices=["cycling", "running", "all"], default="all")
    p.add_argument("--min-tss", type=float, default=None)
    p.add_argument("--limit", type=int, default=None)
    return p.parse_args(argv)


def main(argv: list[str]) -> None:
    args = _parse_args(argv)
    since = _parse_since(args.since)

    sport_filter = ""
    sport_params: tuple[Any, ...] = ()
    if args.sport == "cycling":
        sport_filter = " AND lower(sport) IN (" + ",".join("?" * len(CYCLING_SPORTS)) + ")"
        sport_params = tuple(CYCLING_SPORTS)
    elif args.sport == "running":
        sport_filter = " AND lower(sport) IN (" + ",".join("?" * len(RUNNING_SPORTS)) + ")"
        sport_params = tuple(RUNNING_SPORTS)

    tss_filter = ""
    tss_params: tuple[Any, ...] = ()
    if args.min_tss is not None:
        tss_filter = " AND tss >= ?"
        tss_params = (args.min_tss,)

    limit_clause = f" LIMIT {int(args.limit)}" if args.limit else ""

    sql = (
        "SELECT id, source, source_id, sport, start_utc, duration_s, distance_m, "
        "avg_power, np, intensity_factor, tss, tss_kind, kj, avg_hr, max_hr, "
        "elevation_gain_m, np_low_confidence "
        f"FROM activities WHERE start_utc >= ? {sport_filter}{tss_filter} "
        f"ORDER BY start_utc DESC{limit_clause}"
    )
    with open_db() as conn:
        rows = conn.execute(sql, (since, *sport_params, *tss_params)).fetchall()

    out = []
    for r in rows:
        d = dict(r)
        d["duration_min"] = round((d["duration_s"] or 0) / 60, 1)
        if d.get("distance_m"):
            d["distance_km"] = round(d["distance_m"] / 1000.0, 2)
        out.append(d)

    emit({"count": len(out), "since": since, "activities": out})


if __name__ == "__main__":
    main(sys.argv[1:])

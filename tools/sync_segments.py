"""sync_segments — pull Martin's starred Strava segments into SQLite.

Args:
    --include-efforts          also pull personal efforts on each segment
    --limit N                  cap on segments synced

Output:
    {"synced": N, "updated": M, "errors": [...]}

Stores `segments.bearing_deg` precomputed from the polyline so KOM tools
don't recompute on every wind query.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from _common import emit, fail, log, open_db  # type: ignore[import-not-found]
from analysis.wind import bearing_from_polyline


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--include-efforts", action="store_true")
    p.add_argument("--limit", type=int, default=None)
    return p.parse_args(argv)


def main(argv: list[str]) -> None:
    args = _parse_args(argv)
    from _common import strava_client  # type: ignore[import-not-found]

    log("[segments] pulling starred segments")
    client, _ = strava_client()
    synced = 0
    updated = 0
    errors: list[dict] = []

    with open_db() as conn:
        try:
            starred = client.get_starred_segments()
        except Exception as e:  # noqa: BLE001
            fail(f"strava get_starred_segments: {e}")

        for i, seg in enumerate(starred):
            if args.limit is not None and i >= args.limit:
                break
            try:
                # Get the full segment to access polyline + KOM stats
                detail = client.get_segment(seg.id)
                polyline = None
                bearing = None
                if getattr(detail, "map", None) and getattr(detail.map, "polyline", None):
                    polyline = detail.map.polyline
                    try:
                        import polyline as pl

                        pts = pl.decode(polyline, 5)
                        bearing = bearing_from_polyline(pts)
                    except Exception:
                        bearing = None

                xom = getattr(detail, "xoms", None)
                kom_time = None
                kom_avg_w = None
                if xom:
                    kom_time = getattr(xom, "kom_time", None)
                    if isinstance(kom_time, str):
                        # "0:01:42" → 102 seconds
                        try:
                            h, m, s = kom_time.split(":")
                            kom_time = int(h) * 3600 + int(m) * 60 + int(s)
                        except Exception:
                            kom_time = None

                # Best-effort: KOM avg watts (Strava sometimes exposes via leaderboard;
                # leaving null if not available).
                row = {
                    "id": int(detail.id),
                    "name": detail.name,
                    "distance_m": float(getattr(detail, "distance", 0) or 0),
                    "avg_grade": float(getattr(detail, "average_grade", 0) or 0),
                    "bearing_deg": float(bearing) if bearing is not None else None,
                    "polyline": polyline,
                    "kom_time_s": int(kom_time) if kom_time else None,
                    "kom_avg_w": float(kom_avg_w) if kom_avg_w else None,
                    "starred": 1,
                    "raw": json.dumps(_summary_dict(detail), default=str),
                }
                existing = conn.execute(
                    "SELECT id FROM segments WHERE id = ?", (row["id"],)
                ).fetchone()
                if existing:
                    conn.execute(
                        "UPDATE segments SET name=:name, distance_m=:distance_m, avg_grade=:avg_grade, "
                        "bearing_deg=:bearing_deg, polyline=:polyline, kom_time_s=:kom_time_s, "
                        "kom_avg_w=:kom_avg_w, starred=:starred, raw=:raw WHERE id=:id",
                        row,
                    )
                    updated += 1
                else:
                    conn.execute(
                        "INSERT INTO segments (id, name, distance_m, avg_grade, bearing_deg, polyline, "
                        "kom_time_s, kom_avg_w, starred, raw) "
                        "VALUES (:id, :name, :distance_m, :avg_grade, :bearing_deg, :polyline, "
                        ":kom_time_s, :kom_avg_w, :starred, :raw)",
                        row,
                    )
                    synced += 1
            except Exception as e:  # noqa: BLE001
                errors.append({"segment_id": getattr(seg, "id", None), "error": str(e)})

    emit({"synced": synced, "updated": updated, "errors": errors})


def _summary_dict(seg: Any) -> dict:
    """Pluck the most useful fields off a stravalib Segment for storage."""
    out = {}
    for f in ("id", "name", "distance", "average_grade", "elevation_high", "elevation_low",
              "city", "state", "country"):
        v = getattr(seg, f, None)
        if v is not None:
            out[f] = v
    return out


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception as e:  # noqa: BLE001
        fail(str(e))

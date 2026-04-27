"""route_weather — Open-Meteo hourly forecast for a point or polyline.

Args:
    --lat FLOAT --lon FLOAT      single point
    --polyline STR               Strava precision-5 polyline (alternative)
    --hours-ahead N              default: 12 (next 12 hours from now)
    --sample-count N             when polyline given, sample N points (default 5)

Output:
    {
      "queries": [{lat, lon, hourly: [{time, temp_c, wind_kmh, wind_from_deg, precip_mm}]}],
      "fetched_at": "...",
      "cache_used": bool
    }

Caches into `weather_forecast` table keyed by (lat, lon, hour_utc) with
~1 hour staleness window.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys

import httpx
from _common import emit, fail, log, open_db  # type: ignore[import-not-found]


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--lat", type=float)
    p.add_argument("--lon", type=float)
    p.add_argument("--polyline")
    p.add_argument("--hours-ahead", type=int, default=12)
    p.add_argument("--sample-count", type=int, default=5)
    return p.parse_args(argv)


def _resolve_points(args: argparse.Namespace) -> list[tuple[float, float]]:
    if args.polyline:
        try:
            import polyline as pl
        except ImportError:
            fail("polyline package missing — pip install polyline")
        pts = pl.decode(args.polyline, 5)
        if not pts:
            return []
        if len(pts) <= args.sample_count:
            return [tuple(p) for p in pts]
        step = max(1, len(pts) // args.sample_count)
        sampled = [tuple(p) for p in pts[::step]]
        if sampled[-1] != tuple(pts[-1]):
            sampled.append(tuple(pts[-1]))
        return sampled
    if args.lat is None or args.lon is None:
        fail("--lat/--lon or --polyline required")
    return [(args.lat, args.lon)]


def _fetch_one(lat: float, lon: float, hours_ahead: int, conn) -> dict:
    """Open-Meteo hourly fetch with a simple cache."""
    now_utc = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
    target_hours = [now_utc + dt.timedelta(hours=h) for h in range(hours_ahead + 1)]

    # Cache check — return cached rows if all hours are present and <60 min old
    cache_rows = []
    for h_utc in target_hours:
        row = conn.execute(
            "SELECT * FROM weather_forecast WHERE lat = ? AND lon = ? AND hour_utc = ?",
            (round(lat, 4), round(lon, 4), h_utc.isoformat()),
        ).fetchone()
        if row:
            fetched_at = dt.datetime.fromisoformat(row["fetched_at"].replace("Z", "+00:00"))
            if (dt.datetime.now(dt.timezone.utc) - fetched_at).total_seconds() < 3600:
                cache_rows.append(row)
            else:
                cache_rows = []
                break
        else:
            cache_rows = []
            break

    if cache_rows:
        log(f"[weather] cache hit at ({lat:.3f}, {lon:.3f})")
        return {
            "lat": lat,
            "lon": lon,
            "hourly": [
                {
                    "time": r["hour_utc"],
                    "temp_c": r["temp_c"],
                    "wind_kmh": r["wind_kmh"],
                    "wind_from_deg": r["wind_dir_from_deg"],
                    "precip_mm": r["precip_mm"],
                }
                for r in cache_rows
            ],
            "cache_used": True,
        }

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,wind_speed_10m,wind_direction_10m,precipitation",
        "forecast_days": 2,
        "timezone": "UTC",
    }
    log(f"[weather] fetch ({lat:.3f}, {lon:.3f})")
    resp = httpx.get(url, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    h = data["hourly"]
    times = h["time"]
    temps = h["temperature_2m"]
    winds = h["wind_speed_10m"]
    dirs = h["wind_direction_10m"]
    precs = h["precipitation"]

    target_set = {t.isoformat().replace("+00:00", "") for t in target_hours}
    out_rows = []
    fetched_at = dt.datetime.now(dt.timezone.utc).isoformat()

    for ts, t, w, d, p in zip(times, temps, winds, dirs, precs):
        # Open-Meteo returns naïve UTC ISO (no tz) — match by string
        if ts not in target_set and ts + ":00" not in target_set:
            continue
        hour_iso = ts + (":00" if len(ts) <= 16 else "")
        # Insert into cache
        conn.execute(
            "INSERT OR REPLACE INTO weather_forecast (lat, lon, hour_utc, temp_c, wind_kmh, wind_dir_from_deg, precip_mm, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                round(lat, 4),
                round(lon, 4),
                hour_iso,
                t,
                w,
                d,
                p,
                fetched_at,
            ),
        )
        out_rows.append(
            {"time": hour_iso, "temp_c": t, "wind_kmh": w, "wind_from_deg": d, "precip_mm": p}
        )

    return {"lat": lat, "lon": lon, "hourly": out_rows, "cache_used": False}


def main(argv: list[str]) -> None:
    args = _parse_args(argv)
    points = _resolve_points(args)
    if not points:
        fail("no points to query")

    queries = []
    with open_db() as conn:
        for lat, lon in points:
            try:
                queries.append(_fetch_one(lat, lon, args.hours_ahead, conn))
            except Exception as e:  # noqa: BLE001
                queries.append({"lat": lat, "lon": lon, "error": str(e)})

    emit(
        {
            "queries": queries,
            "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
    )


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        fail(str(e))

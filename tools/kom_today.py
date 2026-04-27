"""kom_today — rank starred segments by KOM-attack score for the next N hours.

Args:
    --hours-ahead N            window to consider (default 6)
    --top N                    return top N (default 5)
    --min-distance-m N         skip short sprint segments (default 200)

Output:
    {
      "as_of_utc": "...",
      "segments": [
        {segment_id, name, distance_m, avg_grade, bearing_deg, kom_time_s, kom_avg_w,
         best_hour_utc, score, tail_kmh, cross_kmh, temp_c, precip_mm,
         realistic_threat: bool, reason: "..."}, ...
      ]
    }

For each starred segment, decode the polyline midpoint, fetch the
Open-Meteo hourly forecast at that point, and pick the best score across
the next `hours_ahead` hours. Returns the top `top` ranked.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys

import httpx
from _common import emit, fail, log, open_db  # type: ignore[import-not-found]
from analysis.wind import (
    bearing_from_polyline,
    haversine,
    kom_score,
    realistic_threat,
    wind_components,
)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--hours-ahead", type=int, default=6)
    p.add_argument("--top", type=int, default=5)
    p.add_argument("--min-distance-m", type=float, default=200.0)
    return p.parse_args(argv)


def _decode_midpoint(polyline_str: str | None) -> tuple[float, float] | None:
    if not polyline_str:
        return None
    try:
        import polyline as pl

        pts = pl.decode(polyline_str, 5)
        if not pts:
            return None
        return tuple(pts[len(pts) // 2])
    except Exception:
        return None


def _fetch_hourly(lat: float, lon: float, hours_ahead: int, conn) -> list[dict] | None:
    """Best-effort fetch via the cache + Open-Meteo. Returns up to
    `hours_ahead` hourly dicts."""
    now_utc = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
    target_hours = [now_utc + dt.timedelta(hours=h) for h in range(hours_ahead + 1)]

    rows = []
    missing = False
    for h_utc in target_hours:
        row = conn.execute(
            "SELECT * FROM weather_forecast WHERE lat=? AND lon=? AND hour_utc=?",
            (round(lat, 4), round(lon, 4), h_utc.isoformat()),
        ).fetchone()
        if not row:
            missing = True
            break
        fetched_at = dt.datetime.fromisoformat(row["fetched_at"].replace("Z", "+00:00"))
        if (dt.datetime.now(dt.timezone.utc) - fetched_at).total_seconds() > 3600:
            missing = True
            break
        rows.append(row)

    if not missing:
        return [
            {
                "time": r["hour_utc"],
                "temp_c": r["temp_c"],
                "wind_kmh": r["wind_kmh"],
                "wind_from_deg": r["wind_dir_from_deg"],
                "precip_mm": r["precip_mm"],
            }
            for r in rows
        ]

    # Fetch fresh
    try:
        resp = httpx.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": "temperature_2m,wind_speed_10m,wind_direction_10m,precipitation",
                "forecast_days": 2,
                "timezone": "UTC",
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:  # noqa: BLE001
        log(f"[kom_today] open-meteo fetch failed at ({lat:.3f}, {lon:.3f}): {e}")
        return None

    h = data["hourly"]
    fetched_at = dt.datetime.now(dt.timezone.utc).isoformat()
    target_set = {t.isoformat() for t in target_hours}
    out: list[dict] = []
    for ts, t, w, d, p in zip(
        h["time"], h["temperature_2m"], h["wind_speed_10m"], h["wind_direction_10m"], h["precipitation"]
    ):
        # Match the loose hour-iso strings
        if ts not in target_set and (ts + ":00") not in target_set:
            continue
        hour_iso = ts if len(ts) > 16 else ts + ":00"
        conn.execute(
            "INSERT OR REPLACE INTO weather_forecast (lat, lon, hour_utc, temp_c, wind_kmh, wind_dir_from_deg, precip_mm, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (round(lat, 4), round(lon, 4), hour_iso, t, w, d, p, fetched_at),
        )
        out.append({"time": hour_iso, "temp_c": t, "wind_kmh": w, "wind_from_deg": d, "precip_mm": p})
    return out


def main(argv: list[str]) -> None:
    args = _parse_args(argv)

    with open_db() as conn:
        rows = conn.execute(
            "SELECT id, name, distance_m, avg_grade, bearing_deg, kom_time_s, kom_avg_w, polyline "
            "FROM segments WHERE starred = 1 AND distance_m >= ?",
            (args.min_distance_m,),
        ).fetchall()
        if not rows:
            emit(
                {
                    "as_of_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "segments": [],
                    "note": "no starred segments — run sync_segments.py",
                }
            )
            return

        ranked = []
        for s in rows:
            midpoint = _decode_midpoint(s["polyline"])
            bearing = s["bearing_deg"]
            if midpoint is None or bearing is None:
                continue
            hourly = _fetch_hourly(midpoint[0], midpoint[1], args.hours_ahead, conn)
            if not hourly:
                continue
            best = None
            for hr in hourly:
                comp = wind_components(hr["wind_kmh"], hr["wind_from_deg"], bearing)
                score = kom_score(comp["tail_kmh"], comp["cross_kmh"], hr["temp_c"], hr["precip_mm"])
                if best is None or score > best["score"]:
                    best = {**hr, **comp, "score": score}
            if best is None:
                continue
            threat = realistic_threat(
                user_power_at_kom_time=None,  # power-curve estimation comes later
                kom_avg_w=s["kom_avg_w"],
                tail_kmh=best["tail_kmh"],
                precip_mm=best["precip_mm"] or 0.0,
                segment_length_m=s["distance_m"] or 0.0,
            )
            ranked.append(
                {
                    "segment_id": s["id"],
                    "name": s["name"],
                    "distance_m": s["distance_m"],
                    "avg_grade": s["avg_grade"],
                    "bearing_deg": bearing,
                    "kom_time_s": s["kom_time_s"],
                    "kom_avg_w": s["kom_avg_w"],
                    "best_hour_utc": best["time"],
                    "score": best["score"],
                    "tail_kmh": best["tail_kmh"],
                    "cross_kmh": best["cross_kmh"],
                    "temp_c": best["temp_c"],
                    "precip_mm": best["precip_mm"],
                    "realistic_threat": threat["threat"],
                    "reason": threat["reason"],
                }
            )

    ranked.sort(key=lambda r: r["score"], reverse=True)
    emit(
        {
            "as_of_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "segments": ranked[: args.top],
        }
    )


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        fail(str(e))

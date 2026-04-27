"""kom_threat — score a single segment for KOM attack.

Args:
    --segment-id N             required
    --hour-utc YYYY-MM-DDTHH:00 optional, default: now
    --user-power-w INT         optional override of estimated user power for KOM duration

Output: full detail dict including the wind decomposition along the polyline.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys

from _common import emit, fail, open_db  # type: ignore[import-not-found]
from analysis.wind import (
    kom_score,
    length_weighted_tail,
    realistic_threat,
    wind_components,
)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--segment-id", type=int, required=True)
    p.add_argument("--hour-utc")
    p.add_argument("--user-power-w", type=int)
    return p.parse_args(argv)


def main(argv: list[str]) -> None:
    args = _parse_args(argv)

    with open_db() as conn:
        seg = conn.execute(
            "SELECT id, name, distance_m, avg_grade, bearing_deg, kom_time_s, kom_avg_w, polyline "
            "FROM segments WHERE id = ?",
            (args.segment_id,),
        ).fetchone()
        if seg is None:
            fail(f"segment {args.segment_id} not found — run sync_segments.py first")

        # Decode polyline points
        pts = []
        if seg["polyline"]:
            try:
                import polyline as pl

                pts = [tuple(p) for p in pl.decode(seg["polyline"], 5)]
            except Exception:
                pts = []
        midpoint = pts[len(pts) // 2] if pts else None

        # Fetch (or read from cache) the relevant hour's weather
        target_hour = args.hour_utc or dt.datetime.now(dt.timezone.utc).replace(
            minute=0, second=0, microsecond=0
        ).isoformat()
        if midpoint is None:
            fail("segment has no polyline; cannot determine weather location")
        weather = conn.execute(
            "SELECT * FROM weather_forecast WHERE lat=? AND lon=? AND hour_utc=?",
            (round(midpoint[0], 4), round(midpoint[1], 4), target_hour),
        ).fetchone()
        if weather is None:
            fail(
                f"no cached weather for ({midpoint[0]:.3f},{midpoint[1]:.3f}) at "
                f"{target_hour}; run kom_today or route_weather first"
            )

        wind_kmh = weather["wind_kmh"]
        wind_from = weather["wind_dir_from_deg"]
        temp_c = weather["temp_c"]
        precip_mm = weather["precip_mm"]

        # Two views: simple end-to-end bearing and length-weighted along polyline
        comp_simple = wind_components(wind_kmh, wind_from, seg["bearing_deg"])
        comp_weighted = length_weighted_tail(pts, wind_kmh, wind_from)

        score = kom_score(comp_simple["tail_kmh"], comp_simple["cross_kmh"], temp_c, precip_mm)
        threat = realistic_threat(
            user_power_at_kom_time=args.user_power_w,
            kom_avg_w=seg["kom_avg_w"],
            tail_kmh=comp_simple["tail_kmh"],
            precip_mm=precip_mm or 0.0,
            segment_length_m=seg["distance_m"] or 0.0,
        )

    emit(
        {
            "segment_id": seg["id"],
            "name": seg["name"],
            "distance_m": seg["distance_m"],
            "avg_grade": seg["avg_grade"],
            "bearing_deg": seg["bearing_deg"],
            "kom_time_s": seg["kom_time_s"],
            "kom_avg_w": seg["kom_avg_w"],
            "weather": {
                "hour_utc": target_hour,
                "lat": midpoint[0],
                "lon": midpoint[1],
                "wind_kmh": wind_kmh,
                "wind_from_deg": wind_from,
                "temp_c": temp_c,
                "precip_mm": precip_mm,
            },
            "wind_decomposition": {
                "simple": comp_simple,
                "weighted": comp_weighted,
            },
            "score": score,
            "realistic_threat": threat["threat"],
            "threat_reason": threat["reason"],
            "user_power_w_input": args.user_power_w,
        }
    )


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        fail(str(e))

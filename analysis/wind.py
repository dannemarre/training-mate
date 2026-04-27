"""Wind / yaw / KOM scoring math.

Pure functions; tools/kom_*.py and tools/route_weather.py orchestrate.
See docs/wind-and-kom.md for derivations and citations.
"""
from __future__ import annotations

import math
from typing import Iterable


def bearing_from_polyline(points: list[tuple[float, float]]) -> float:
    """Initial bearing from first point to last — used for short segments
    where a single bearing suffices. Returns degrees in [0, 360)."""
    if len(points) < 2:
        return 0.0
    return _initial_bearing(points[0], points[-1])


def _initial_bearing(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, p1)
    lat2, lon2 = map(math.radians, p2)
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def haversine(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """Great-circle distance in meters."""
    R = 6371000.0
    lat1, lon1 = map(math.radians, p1)
    lat2, lon2 = map(math.radians, p2)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def wind_components(wind_kmh: float, wind_from_deg: float, segment_bearing: float) -> dict:
    """Decompose wind into tail and crosswind components for a rider on a
    segment heading `segment_bearing`. Wind direction is meteorological
    (where it's coming FROM); we convert to "to" before doing geometry.

    Returns:
        {"tail_kmh": float, "cross_kmh": float, "delta_deg": float}
    """
    wind_to = (wind_from_deg + 180) % 360
    delta = ((wind_to - segment_bearing + 540) % 360) - 180  # -180..+180
    tail = wind_kmh * math.cos(math.radians(delta))
    cross = wind_kmh * math.sin(math.radians(delta))
    return {"tail_kmh": round(tail, 2), "cross_kmh": round(cross, 2), "delta_deg": round(delta, 1)}


def length_weighted_tail(
    polyline_points: list[tuple[float, float]],
    wind_kmh: float,
    wind_from_deg: float,
    sample_count: int = 20,
) -> dict:
    """For curving segments, sample the polyline and length-weight the
    tail-wind component along each sub-piece.

    Returns the same dict as `wind_components` but with `tail_kmh` averaged
    by piece length, plus the simple end-to-end bearing for reference.
    """
    if len(polyline_points) < 2:
        return wind_components(wind_kmh, wind_from_deg, 0.0)

    if len(polyline_points) > sample_count:
        step = max(1, len(polyline_points) // sample_count)
        sampled = polyline_points[::step]
        if sampled[-1] != polyline_points[-1]:
            sampled.append(polyline_points[-1])
    else:
        sampled = polyline_points

    pieces = []
    total_length = 0.0
    weighted_tail_sum = 0.0
    for a, b in zip(sampled, sampled[1:]):
        L = haversine(a, b)
        if L < 1.0:
            continue
        bearing = _initial_bearing(a, b)
        comp = wind_components(wind_kmh, wind_from_deg, bearing)
        pieces.append({"bearing": round(bearing, 1), "length_m": round(L, 1), **comp})
        weighted_tail_sum += L * comp["tail_kmh"]
        total_length += L
    if total_length == 0:
        return wind_components(wind_kmh, wind_from_deg, 0.0)
    weighted_tail = weighted_tail_sum / total_length
    return {
        "tail_kmh": round(weighted_tail, 2),
        "cross_kmh": None,
        "delta_deg": None,
        "pieces": pieces,
        "end_to_end_bearing": round(_initial_bearing(sampled[0], sampled[-1]), 1),
    }


def kom_score(tail_kmh: float, cross_kmh: float | None, temp_c: float | None, precip_mm: float | None) -> float:
    """Per docs/wind-and-kom.md: tail bonus, cross drag, sweet-temp +1, rain -3."""
    score = float(tail_kmh)
    if cross_kmh is not None:
        score -= 0.4 * abs(cross_kmh)
    if temp_c is not None and 8 <= temp_c <= 18:
        score += 1.0
    if precip_mm is not None and precip_mm > 0.5:
        score -= 3.0
    return round(score, 2)


def realistic_threat(
    user_power_at_kom_time: float | None,
    kom_avg_w: float | None,
    tail_kmh: float,
    precip_mm: float,
    segment_length_m: float,
    cushion: float = 0.97,
    min_tail_kmh: float = 4.0,
) -> dict:
    """Per docs/wind-and-kom.md threat threshold."""
    if not (user_power_at_kom_time and kom_avg_w):
        return {"threat": False, "reason": "missing power data"}
    if segment_length_m < 200:
        return {"threat": False, "reason": "segment too short — sprint dynamics, not endurance"}
    if precip_mm > 0.5:
        return {"threat": False, "reason": f"precip {precip_mm:.1f}mm too heavy"}
    if tail_kmh <= min_tail_kmh:
        return {"threat": False, "reason": f"tail {tail_kmh:.1f}km/h below {min_tail_kmh}"}
    if user_power_at_kom_time < cushion * kom_avg_w:
        gap_pct = (kom_avg_w - user_power_at_kom_time) / kom_avg_w * 100
        return {"threat": False, "reason": f"power gap {gap_pct:.1f}% below cushion ({cushion*100:.0f}% of KOM avg)"}
    return {"threat": True, "reason": "tailwind + power within cushion + clear weather"}

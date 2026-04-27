"""Fueling math — carbs, fluids, sodium per `docs/fueling.md`.

Pure functions; tools/fuel_plan.py orchestrates.
"""
from __future__ import annotations

from typing import Any


def carbs_per_hour(intensity_factor: float) -> int:
    """g/h based on IF. clamp(60 + 30·IF, 60, 120)."""
    return int(round(max(60.0, min(120.0, 60.0 + 30.0 * intensity_factor))))


def fluids_per_hour(temp_c: float | None) -> int:
    """ml/h. 500 base, +250 if temp_c > 22, +250 more if > 28."""
    if temp_c is None:
        return 500
    base = 500
    if temp_c > 22:
        base += 250
    if temp_c > 28:
        base += 250
    return base


def sodium_per_hour(temp_c: float | None, heavy_sweater: bool = False) -> int:
    """mg/h. 600 base; +300 if hot; +200 if heavy sweater; floor 400 cold."""
    base = 600
    if temp_c is not None:
        if temp_c > 25:
            base += 300
        if temp_c < 5:
            base = 400  # less sweat loss; reduce baseline
    if heavy_sweater:
        base += 200
    return base


def pre_ride_carbs(weight_kg: float) -> int:
    """1.5 × weight_kg, eaten 1-3 h before."""
    return int(round(1.5 * weight_kg))


def post_ride(weight_kg: float) -> dict[str, int]:
    """1.0 × kg carbs + 0.3 × kg protein within 60 min."""
    return {
        "carbs_g": int(round(1.0 * weight_kg)),
        "protein_g": int(round(0.3 * weight_kg)),
    }


def hourly_table(duration_h: float, intensity_factor: float, temp_c: float | None,
                 heavy_sweater: bool = False) -> list[dict[str, Any]]:
    """Per-hour plan. Hour 1 ramps up; subsequent hours hit target."""
    target = carbs_per_hour(intensity_factor)
    fluids = fluids_per_hour(temp_c)
    sodium = sodium_per_hour(temp_c, heavy_sweater)
    out = []
    full_hours = int(duration_h)
    last_hour_fraction = duration_h - full_hours
    for h in range(1, full_hours + 1):
        if h == 1:
            note = "build up gradually — don't overeat early"
            carbs = max(60, int(round(target * 0.85)))
        elif h == full_hours:
            note = "final hour — maintain or scale slightly down"
            carbs = target
        else:
            note = "target rate"
            carbs = target
        out.append({"hour": h, "carbs_g": carbs, "fluids_ml": fluids, "sodium_mg": sodium, "note": note})
    if last_hour_fraction > 0.05:
        out.append({
            "hour": full_hours + 1,
            "carbs_g": int(round(target * last_hour_fraction)),
            "fluids_ml": int(round(fluids * last_hour_fraction)),
            "sodium_mg": int(round(sodium * last_hour_fraction)),
            "note": f"partial hour ({last_hour_fraction:.1f}h)",
        })
    return out


def plan(duration_h: float, intensity_factor: float, temp_c: float | None,
         weight_kg: float, heavy_sweater: bool = False) -> dict[str, Any]:
    """Full fueling plan."""
    target_cph = carbs_per_hour(intensity_factor)
    fluids_h = fluids_per_hour(temp_c)
    sodium_h = sodium_per_hour(temp_c, heavy_sweater)
    table = hourly_table(duration_h, intensity_factor, temp_c, heavy_sweater)
    pre = pre_ride_carbs(weight_kg)
    post = post_ride(weight_kg)
    return {
        "duration_h": duration_h,
        "IF": intensity_factor,
        "temp_c": temp_c,
        "weight_kg": weight_kg,
        "heavy_sweater": heavy_sweater,
        "carbs_g_per_h": target_cph,
        "fluids_ml_per_h": fluids_h,
        "sodium_mg_per_h": sodium_h,
        "pre_ride_carbs_g": pre,
        "post_ride_carbs_g": post["carbs_g"],
        "post_ride_protein_g": post["protein_g"],
        "carbs_g_total": sum(r["carbs_g"] for r in table),
        "fluids_ml_total": sum(r["fluids_ml"] for r in table),
        "sodium_mg_total": sum(r["sodium_mg"] for r in table),
        "hourly_table": table,
        "hot_day": temp_c is not None and temp_c > 25,
        "cold_day": temp_c is not None and temp_c < 5,
    }

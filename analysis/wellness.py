"""Wellness gating math — HRV rolling baseline, sleep, RHR drift.

Pure functions; tools/daily_briefing.py orchestrates. See docs/wellness.md
for the canonical rules (Plews/Buchheit-style multi-day baseline + SWC).
"""
from __future__ import annotations

import statistics
from typing import Iterable, NamedTuple


class HrvState(NamedTuple):
    state: str           # "normal" | "swap_hard_for_z2" | "easy_only" | "recovery_required" | "no_baseline"
    breach_days: int
    baseline_7d: float | None
    swc: float | None
    today: float | None


def hrv_state(today_rmssd: float | None, history_7d: Iterable[float]) -> HrvState:
    """Plews/Buchheit gating rule.

    baseline_7d = mean(history_7d)
    swc         = 0.5 × stdev(history_7d)
    Today + history are checked for *consecutive* breaches of the lower bound.

    State table:
      breaches ≥ 4   → "recovery_required"
      breaches = 3   → "easy_only"
      breaches = 2   → "swap_hard_for_z2"
      else           → "normal"

    "No baseline" returns state="no_baseline" — don't gate on HRV until
    you have at least 5 nights of data.
    """
    history = [float(x) for x in history_7d if x is not None]
    if len(history) < 5:
        return HrvState(
            state="no_baseline",
            breach_days=0,
            baseline_7d=None,
            swc=None,
            today=today_rmssd,
        )

    baseline = statistics.mean(history)
    raw_swc = 0.5 * statistics.pstdev(history) if len(history) > 1 else 0.0
    # Floor SWC at 3% of baseline. With very stable histories (e.g. low
    # day-to-day variability) raw SWC can be tight enough that values
    # nominally inside the band still trip the threshold. Plews/Buchheit's
    # rule is meant to detect *meaningful* dips; the floor keeps us out of
    # noise-grade swings.
    swc = max(raw_swc, baseline * 0.03)
    threshold = baseline - swc

    # Walk *backwards* from today to count the consecutive breach streak.
    series = list(history)
    if today_rmssd is not None:
        series.append(float(today_rmssd))
    streak = 0
    for v in reversed(series):
        if v is None:
            break
        if v < threshold:
            streak += 1
        else:
            break

    if streak >= 4:
        state = "recovery_required"
    elif streak == 3:
        state = "easy_only"
    elif streak == 2:
        state = "swap_hard_for_z2"
    else:
        state = "normal"

    return HrvState(
        state=state,
        breach_days=streak,
        baseline_7d=baseline,
        swc=swc,
        today=today_rmssd,
    )


def sleep_advisory(sleep_minutes: int | None, prior_night_minutes: int | None = None) -> dict:
    """Map sleep duration → advisory state per docs/wellness.md."""
    if sleep_minutes is None:
        return {"state": "unknown", "note": "no sleep data"}
    h = sleep_minutes / 60.0
    if h < 5:
        return {"state": "recovery_only", "note": f"only {h:.1f} h — recovery only, no Z3+"}
    if h < 6:
        if prior_night_minutes is not None and prior_night_minutes / 60.0 < 6:
            return {
                "state": "easy_only",
                "note": "two consecutive nights <6 h — easy only",
            }
        return {"state": "no_z4_plus", "note": f"{h:.1f} h — drop Z4+ today"}
    if h < 7:
        return {"state": "soft_caution", "note": f"{h:.1f} h — consider scaling intensity"}
    return {"state": "ok", "note": f"{h:.1f} h — solid"}


def rhr_drift(rhr_today: int | None, history_14d: Iterable[int | float]) -> dict:
    """RHR elevated >5 bpm above 14-day mean → soft flag."""
    history = [float(x) for x in history_14d if x is not None]
    if rhr_today is None or len(history) < 5:
        return {"flag": False, "delta": None, "baseline": None}
    baseline = statistics.mean(history)
    delta = float(rhr_today) - baseline
    return {
        "flag": delta > 5.0,
        "delta": round(delta, 1),
        "baseline": round(baseline, 1),
    }

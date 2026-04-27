"""PMC math — Banister exp-weighted CTL/ATL/TSB.

Pure functions, no DB. Tools under `tools/` orchestrate; this module computes.

Definitions (per docs/training-science.md):
  CTL[d] = CTL[d-1] + (TSS[d] - CTL[d-1]) / 42      # 42-day τ — fitness
  ATL[d] = ATL[d-1] + (TSS[d] - ATL[d-1]) /  7      #  7-day τ — fatigue
  TSB[d] = CTL[d-1] - ATL[d-1]                       #          form
"""
from __future__ import annotations

import datetime as dt
from typing import Iterable, NamedTuple

CTL_TAU_DAYS = 42
ATL_TAU_DAYS = 7


class PmcDay(NamedTuple):
    date: dt.date
    tss: float
    ctl: float
    atl: float
    tsb: float


def compute_pmc(
    daily_tss: Iterable[tuple[dt.date, float]],
    seed_ctl: float = 0.0,
    seed_atl: float = 0.0,
) -> list[PmcDay]:
    """Compute CTL/ATL/TSB across an ordered date series.

    Args:
        daily_tss: iterable of (date, total_tss_for_day) tuples, sorted by date
            ascending. Days with no activity should still appear with tss=0
            so the decay applies.
        seed_ctl: initial CTL on the day BEFORE the first entry.
        seed_atl: initial ATL on the day BEFORE the first entry.

    Returns:
        list[PmcDay] in date order. TSB on day d uses CTL/ATL from day d-1
        (the standard Banister convention).
    """
    out: list[PmcDay] = []
    prev_ctl = float(seed_ctl)
    prev_atl = float(seed_atl)
    for date, tss in daily_tss:
        tss_f = float(tss)
        # TSB before applying today's TSS: yesterday's CTL minus yesterday's ATL.
        tsb = prev_ctl - prev_atl
        ctl = prev_ctl + (tss_f - prev_ctl) / CTL_TAU_DAYS
        atl = prev_atl + (tss_f - prev_atl) / ATL_TAU_DAYS
        out.append(PmcDay(date=date, tss=tss_f, ctl=ctl, atl=atl, tsb=tsb))
        prev_ctl = ctl
        prev_atl = atl
    return out


def fill_missing_days(
    sparse: list[tuple[dt.date, float]],
    start: dt.date,
    end: dt.date,
) -> list[tuple[dt.date, float]]:
    """Expand a sparse list of (date, tss) to a contiguous daily series.

    Days with no entry get tss=0. Ensures CTL/ATL decay correctly across
    rest days. `start` and `end` are inclusive.
    """
    by_date: dict[dt.date, float] = {}
    for d, tss in sparse:
        by_date[d] = by_date.get(d, 0.0) + float(tss)
    days: list[tuple[dt.date, float]] = []
    cur = start
    one_day = dt.timedelta(days=1)
    while cur <= end:
        days.append((cur, by_date.get(cur, 0.0)))
        cur += one_day
    return days


def ramp_7d(daily_pmc: list[PmcDay], on_date: dt.date) -> float | None:
    """CTL today minus CTL 7 days ago. Used by current_form.py for the
    ramp_warning gate (>+8 = warn; >+10 sustained 7d = crash territory)."""
    if not daily_pmc:
        return None
    by_date = {p.date: p.ctl for p in daily_pmc}
    seven_days_ago = on_date - dt.timedelta(days=7)
    if on_date not in by_date or seven_days_ago not in by_date:
        return None
    return by_date[on_date] - by_date[seven_days_ago]


def form_state(tsb: float, ramp_7d: float | None) -> str:
    """Map (TSB, 7-day CTL ramp) → a coachable label.

    See docs/training-science.md for the canonical thresholds.
    """
    if ramp_7d is not None and ramp_7d > 10:
        return "crashing"
    if tsb < -40:
        return "risky"
    if tsb < -30:
        return "overreached"
    if tsb < -10:
        return "productive"
    if tsb < +5:
        return "neutral"
    if tsb <= +20:
        return "race-ready"
    return "detrained"

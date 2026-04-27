"""Tests for analysis/pmc.py — Banister exponential model."""
from __future__ import annotations

import datetime as dt

import pytest

from analysis.pmc import (
    ATL_TAU_DAYS,
    CTL_TAU_DAYS,
    compute_pmc,
    fill_missing_days,
    form_state,
    ramp_7d,
)


def _series(days: int, tss_per_day: float, start: dt.date | None = None):
    start = start or dt.date(2026, 1, 1)
    return [(start + dt.timedelta(days=i), tss_per_day) for i in range(days)]


def test_constant_50_tss_asymptotes_to_50():
    """PMC self-check: ~5τ days (210+) at 50 TSS → CTL≈50, ATL≈50, TSB≈0.

    With CTL τ=42, after 60 days only ~76% of the TSS load is reflected;
    you need roughly 250 days (≈6τ) for CTL to settle within 0.5 of TSS.
    """
    out = compute_pmc(_series(250, 50.0))
    last = out[-1]
    assert last.ctl == pytest.approx(50.0, abs=0.2)
    assert last.atl == pytest.approx(50.0, abs=1e-6)
    assert last.tsb == pytest.approx(0.0, abs=0.2)


def test_atl_converges_faster_than_ctl():
    """ATL (7d τ) reaches steady state ~6× faster than CTL (42d τ)."""
    out = compute_pmc(_series(30, 50.0))
    # After 30 days, ATL is essentially steady; CTL is still climbing.
    assert out[-1].atl == pytest.approx(50.0, abs=0.5)
    assert out[-1].ctl < 30.0  # still well short of 50


def test_zero_tss_decays_both():
    """Starting from CTL=ATL=50, 60 days of zero TSS → both decay toward 0."""
    out = compute_pmc(_series(60, 0.0), seed_ctl=50.0, seed_atl=50.0)
    last = out[-1]
    assert last.ctl < 15  # decayed from 50 with τ=42
    assert last.atl < 0.1  # decayed from 50 with τ=7 (much faster)
    assert last.tsb > 0


def test_tsb_uses_yesterdays_ctl_atl():
    """TSB on day d = CTL[d-1] - ATL[d-1] (Banister convention)."""
    # Seed both to 50; load a 100 TSS day.
    out = compute_pmc([(dt.date(2026, 1, 1), 100.0)], seed_ctl=50.0, seed_atl=50.0)
    # Day 1's TSB = yesterday's CTL (50) - yesterday's ATL (50) = 0.
    assert out[0].tsb == pytest.approx(0.0)


def test_ramp_7d_zero_for_constant_load():
    out = compute_pmc(_series(20, 50.0))
    on_date = out[-1].date
    delta = ramp_7d(out, on_date)
    # CTL has been climbing slowly all 20 days, so ramp_7d > 0 — but it
    # should be modest.
    assert delta is not None
    assert 0 < delta < 10


def test_ramp_7d_positive_after_jump():
    """A 14-day jump from 30 TSS to 80 TSS produces a clear positive ramp_7d."""
    series = _series(20, 30.0) + _series(14, 80.0, start=dt.date(2026, 1, 21))
    out = compute_pmc(series)
    delta = ramp_7d(out, out[-1].date)
    assert delta is not None
    # CTL is climbing fast; ramp should be solidly positive.
    assert delta > 1.5


def test_fill_missing_days_inserts_zero_tss_days():
    sparse = [(dt.date(2026, 1, 1), 50.0), (dt.date(2026, 1, 5), 80.0)]
    filled = fill_missing_days(sparse, dt.date(2026, 1, 1), dt.date(2026, 1, 7))
    assert len(filled) == 7
    assert filled[0] == (dt.date(2026, 1, 1), 50.0)
    assert filled[1][1] == 0.0
    assert filled[4] == (dt.date(2026, 1, 5), 80.0)


def test_fill_missing_days_aggregates_same_day_entries():
    """If two activities land on the same day, their TSS sums."""
    sparse = [(dt.date(2026, 1, 3), 30.0), (dt.date(2026, 1, 3), 45.0)]
    filled = fill_missing_days(sparse, dt.date(2026, 1, 1), dt.date(2026, 1, 5))
    by_date = dict(filled)
    assert by_date[dt.date(2026, 1, 3)] == 75.0


@pytest.mark.parametrize("tsb,ramp,expected", [
    (-50, 0,    "risky"),
    (-35, 0,    "overreached"),
    (-15, 0,    "productive"),
    (  0, 0,    "neutral"),
    ( +8, 0,    "race-ready"),
    (+18, 0,    "race-ready"),
    (+25, 0,    "detrained"),
    ( -5, +12,  "crashing"),   # ramp override
])
def test_form_state_buckets(tsb, ramp, expected):
    assert form_state(tsb, ramp) == expected

"""Tests for analysis/tss.py — pure-function math.

Synthetic constant-power and constant-HR rides validate the formulas.
Golden FIT-file tests are deferred until we have a Golden Cheetah fixture.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from analysis.tss import (
    NP_LOW_CONF_MAX,
    NP_UNRELIABLE_MIN,
    hr_tss_avg,
    hr_tss_trimp,
    normalised_power,
    pace_tss,
    power_tss,
)


# ----- power_tss -------------------------------------------------------------


def test_constant_power_at_ftp_one_hour_yields_100_tss():
    """A 1-hour ride at exactly FTP should produce TSS=100, IF=1.0, NP=FTP."""
    power = np.full(3600, 200, dtype=float)  # 1 h @ 200 W
    result = power_tss(power, ftp=200, sample_hz=1.0)
    assert result["tss"] == pytest.approx(100.0, rel=1e-6)
    assert result["intensity_factor"] == pytest.approx(1.0, rel=1e-6)
    assert result["np"] == pytest.approx(200.0, rel=1e-6)
    assert result["kj"] == pytest.approx(720.0, rel=1e-6)  # 200W × 3600s / 1000
    assert result["duration_s"] == 3600
    assert result["np_unreliable"] is False
    assert result["np_low_confidence"] is False


def test_constant_power_below_ftp_scales_quadratically():
    """30 min @ 0.7 FTP → TSS = 0.5h × 0.49 × 100 = 24.5."""
    power = np.full(1800, 140, dtype=float)  # 30 min @ 140 W with FTP=200
    result = power_tss(power, ftp=200, sample_hz=1.0)
    assert result["tss"] == pytest.approx(0.5 * 0.7**2 * 100, rel=1e-3)
    assert result["intensity_factor"] == pytest.approx(0.7, rel=1e-6)


def test_short_ride_flags_np_unreliable():
    """5-min ride flags np_unreliable; doesn't flag np_low_confidence."""
    power = np.full(300, 200, dtype=float)
    result = power_tss(power, ftp=200, sample_hz=1.0)
    assert result["np_unreliable"] is True
    assert result["np_low_confidence"] is False


def test_15min_ride_flags_low_confidence_only():
    """15-min ride flags np_low_confidence (10–20 min band)."""
    power = np.full(900, 200, dtype=float)
    result = power_tss(power, ftp=200, sample_hz=1.0)
    assert result["np_unreliable"] is False
    assert result["np_low_confidence"] is True


def test_25min_ride_no_flags():
    """25-min ride: no NP confidence flags."""
    power = np.full(1500, 200, dtype=float)
    result = power_tss(power, ftp=200, sample_hz=1.0)
    assert result["np_unreliable"] is False
    assert result["np_low_confidence"] is False


def test_normalised_power_higher_than_average_for_variable_ride():
    """NP > mean for a ride with variability (the whole point of NP)."""
    # 50/50 between 100W and 300W — same average as constant 200W, but more spiky
    spiky = np.tile(np.concatenate([np.full(60, 100.0), np.full(60, 300.0)]), 30)
    flat = np.full(len(spiky), 200, dtype=float)
    np_spiky = normalised_power(spiky)
    np_flat = normalised_power(flat)
    assert np_spiky > np_flat
    assert np_flat == pytest.approx(200.0, rel=1e-6)


def test_zero_ftp_raises():
    with pytest.raises(ValueError):
        power_tss(np.full(60, 200, dtype=float), ftp=0)


def test_empty_power_yields_zero():
    """Empty stream: TSS=0, NP=0, no exception."""
    result = power_tss(np.array([], dtype=float), ftp=200)
    assert result["tss"] == 0.0
    assert result["np"] == 0.0
    assert result["duration_s"] == 0


# ----- hr_tss_trimp ----------------------------------------------------------


def test_hr_trimp_at_lthr_for_one_hour_yields_100():
    """1 hour at exactly LTHR → hrTSS = 100."""
    hr = np.full(3600, 165, dtype=float)
    result = hr_tss_trimp(hr, lthr=165, max_hr=190, rhr=50, sample_hz=1.0)
    assert result["tss"] == pytest.approx(100.0, rel=1e-6)


def test_hr_trimp_below_lthr_yields_lower_tss():
    """30 min at lower HR: TSS < 100."""
    hr = np.full(1800, 130, dtype=float)
    result = hr_tss_trimp(hr, lthr=165, max_hr=190, rhr=50, sample_hz=1.0)
    assert result["tss"] < 50  # well below half of 100


def test_hr_trimp_invalid_anchors_raises():
    with pytest.raises(ValueError):
        hr_tss_trimp(np.full(60, 130, dtype=float), lthr=165, max_hr=50, rhr=50)
    with pytest.raises(ValueError):
        hr_tss_trimp(np.full(60, 130, dtype=float), lthr=200, max_hr=190, rhr=50)


# ----- hr_tss_avg (summary fallback) ----------------------------------------


def test_hr_avg_at_lthr_for_one_hour_yields_100():
    """1 hour @ avg HR = LTHR → hrTSS=100."""
    result = hr_tss_avg(avg_hr=165, duration_s=3600, lthr=165)
    assert result["tss"] == pytest.approx(100.0, rel=1e-6)


def test_hr_avg_quadratic_scaling():
    """45 min @ 0.8 LTHR → TSS = 0.75 × 0.64 × 100 = 48."""
    result = hr_tss_avg(avg_hr=132, duration_s=2700, lthr=165)
    assert result["tss"] == pytest.approx(0.75 * 0.8**2 * 100, rel=1e-3)


# ----- pace_tss --------------------------------------------------------------


def test_pace_tss_at_threshold_for_one_hour_yields_100():
    """1 hour at exactly threshold pace → rTSS=100."""
    # threshold = 4:00/km = 240 s/km → in 1h cover 15 km
    result = pace_tss(distance_m=15000, duration_s=3600, threshold_pace_s_per_km=240)
    assert result["tss"] == pytest.approx(100.0, rel=1e-6)


def test_pace_tss_slower_than_threshold():
    """30 min at 5:00/km (slower) when threshold is 4:00/km → IF=0.8, TSS=32."""
    # 30 min at 5:00/km = 6 km
    result = pace_tss(distance_m=6000, duration_s=1800, threshold_pace_s_per_km=240)
    assert result["intensity_factor"] == pytest.approx(0.8, rel=1e-3)
    assert result["tss"] == pytest.approx(0.5 * 0.8**2 * 100, rel=1e-3)


def test_pace_tss_zero_distance_zero_tss():
    result = pace_tss(distance_m=0, duration_s=1800, threshold_pace_s_per_km=240)
    assert result["tss"] == 0.0


# ----- threshold-band coverage ----------------------------------------------


@pytest.mark.parametrize("duration_s,unreliable,low_conf", [
    (300,  True,  False),  #  5 min
    (599,  True,  False),  #  9:59
    (600,  False, True),   # 10:00
    (1199, False, True),   # 19:59
    (1200, False, False),  # 20:00
    (3600, False, False),  # 60:00
])
def test_np_threshold_bands(duration_s, unreliable, low_conf):
    power = np.full(duration_s, 200, dtype=float)
    result = power_tss(power, ftp=200)
    assert result["np_unreliable"] is unreliable, f"at {duration_s}s"
    assert result["np_low_confidence"] is low_conf, f"at {duration_s}s"

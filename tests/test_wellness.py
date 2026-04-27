"""Tests for analysis/wellness.py — HRV gating, sleep, RHR drift."""
from __future__ import annotations

import pytest

from analysis.wellness import hrv_state, rhr_drift, sleep_advisory


def test_hrv_normal_today_in_baseline():
    # 7 days of stable rMSSD ~ 50, today also 50
    state = hrv_state(50, [48, 49, 50, 51, 52, 50, 49])
    assert state.state == "normal"
    assert state.breach_days == 0


def test_hrv_one_day_below_does_not_flag():
    # Single dip below baseline-SWC is noise per docs/wellness.md
    state = hrv_state(35, [48, 49, 50, 51, 52, 50, 49])
    assert state.state == "normal"
    assert state.breach_days == 1


def test_hrv_two_consecutive_breaches_swap_hard():
    # History ends with a breach, today another breach
    state = hrv_state(35, [48, 49, 50, 51, 52, 50, 36])
    assert state.state == "swap_hard_for_z2"
    assert state.breach_days == 2


def test_hrv_three_breaches_easy_only():
    state = hrv_state(35, [48, 49, 50, 51, 52, 36, 35])
    assert state.state == "easy_only"
    assert state.breach_days == 3


def test_hrv_four_breaches_recovery_required():
    state = hrv_state(35, [48, 49, 50, 51, 36, 35, 34])
    assert state.state == "recovery_required"
    assert state.breach_days == 4


def test_hrv_no_baseline_too_little_history():
    state = hrv_state(50, [48, 49])  # only 2 datapoints
    assert state.state == "no_baseline"


# --- sleep ------------------------------------------------------------------


def test_sleep_ok_at_seven_hours():
    assert sleep_advisory(420)["state"] == "ok"


def test_sleep_soft_caution_at_six_to_seven():
    assert sleep_advisory(380)["state"] == "soft_caution"


def test_sleep_no_z4_plus_at_five_to_six():
    assert sleep_advisory(350)["state"] == "no_z4_plus"


def test_sleep_two_short_nights_escalate_to_easy_only():
    assert sleep_advisory(330, prior_night_minutes=320)["state"] == "easy_only"


def test_sleep_recovery_only_below_five():
    assert sleep_advisory(280)["state"] == "recovery_only"


def test_sleep_unknown_when_no_data():
    assert sleep_advisory(None)["state"] == "unknown"


# --- rhr drift --------------------------------------------------------------


def test_rhr_drift_no_flag_at_baseline():
    out = rhr_drift(50, [49, 50, 51, 50, 50, 49, 51, 50])
    assert out["flag"] is False
    assert out["delta"] == pytest.approx(0.0, abs=0.5)


def test_rhr_drift_flags_above_5_bpm():
    out = rhr_drift(58, [49, 50, 51, 50, 50, 49, 51, 50])
    assert out["flag"] is True
    assert out["delta"] >= 5


def test_rhr_drift_no_data_no_flag():
    assert rhr_drift(None, [49, 50, 51])["flag"] is False
    assert rhr_drift(50, [])["flag"] is False

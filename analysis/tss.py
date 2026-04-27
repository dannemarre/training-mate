"""TSS / NP / IF math (Coggan + TRIMP + pace).

Formulas in `docs/training-science.md`. Pure-function, numpy-only — no DB
or network. The CLI tools under `tools/` are responsible for fetching the
streams, calling these, and writing rows.

Two-tier NP confidence flag (per docs/training-science.md):
  duration <  10 min  →  np_unreliable=True   (don't report TSS-from-power)
  duration < 20 min   →  np_low_confidence=True
  duration ≥ 20 min   →  no flag
"""
from __future__ import annotations

from typing import Any

import numpy as np

NP_UNRELIABLE_MIN = 600   # < 10 min
NP_LOW_CONF_MAX = 1200    # < 20 min


def normalised_power(power: np.ndarray, sample_hz: float = 1.0) -> float:
    """Coggan Normalised Power.

    NP = ( mean( rolling_mean(power, 30s)**4 ) )**0.25

    Args:
        power: 1-D numpy array of watts, one sample per `1/sample_hz` seconds.
        sample_hz: sample rate in Hz (1.0 for typical 1-second samples).

    Returns:
        NP in watts (float). For arrays shorter than the 30-second window,
        returns the simple mean as a sane fallback.
    """
    if len(power) == 0:
        return 0.0
    window = max(1, int(round(30 * sample_hz)))
    if len(power) < window:
        return float(np.mean(power))
    # 30-s rolling mean via cumulative sum trick (vectorised, fast)
    cumsum = np.cumsum(np.insert(power.astype(float), 0, 0))
    rolling = (cumsum[window:] - cumsum[:-window]) / window
    return float((np.mean(rolling**4)) ** 0.25)


def power_tss(power: np.ndarray, ftp: float, sample_hz: float = 1.0) -> dict[str, Any]:
    """Coggan TSS from a power stream.

    Args:
        power: 1-D numpy array of watts.
        ftp: athlete's FTP in watts (must be > 0).
        sample_hz: sample rate of `power`.

    Returns:
        {
          "tss": float,
          "np": float,
          "intensity_factor": float,
          "kj": float,
          "duration_s": int,
          "np_unreliable": bool,       # duration < 10 min
          "np_low_confidence": bool,   # 10 min ≤ duration < 20 min
        }
    """
    if ftp <= 0:
        raise ValueError(f"FTP must be > 0, got {ftp}")
    duration_s = len(power) / sample_hz
    duration_h = duration_s / 3600.0
    np_value = normalised_power(power, sample_hz)
    if_value = np_value / ftp
    tss = duration_h * if_value**2 * 100.0
    kj = float(np.sum(power.astype(float)) / sample_hz / 1000.0)
    return {
        "tss": tss,
        "np": np_value,
        "intensity_factor": if_value,
        "kj": kj,
        "duration_s": int(duration_s),
        "np_unreliable": duration_s < NP_UNRELIABLE_MIN,
        "np_low_confidence": NP_UNRELIABLE_MIN <= duration_s < NP_LOW_CONF_MAX,
    }


def hr_tss_trimp(
    hr: np.ndarray,
    lthr: float,
    max_hr: float,
    rhr: float,
    sample_hz: float = 1.0,
) -> dict[str, Any]:
    """Banister TRIMP-based hrTSS.

    trimp = sum( dt * hrr * 0.64 * exp(1.92 * hrr) )
    hrr   = (hr - rhr) / (max_hr - rhr)
    hrTSS = trimp / trimp_at_lthr_for_1h * 100

    Args:
        hr: 1-D numpy array of bpm.
        lthr, max_hr, rhr: athlete profile values in bpm.
        sample_hz: sample rate of `hr`.

    Returns:
        {"tss": float, "trimp": float, "duration_s": int}
    """
    if max_hr <= rhr:
        raise ValueError(f"max_hr ({max_hr}) must be > rhr ({rhr})")
    if lthr <= rhr or lthr > max_hr:
        raise ValueError(f"lthr ({lthr}) must satisfy rhr < lthr ≤ max_hr")

    dt = 1.0 / sample_hz
    duration_s = len(hr) / sample_hz
    if len(hr) == 0:
        return {"tss": 0.0, "trimp": 0.0, "duration_s": 0}

    hrr = (hr.astype(float) - rhr) / (max_hr - rhr)
    hrr = np.clip(hrr, 0.0, None)  # clip negative values (HR < RHR)
    weight = 0.64 * np.exp(1.92 * hrr)
    trimp = float(np.sum(dt * hrr * weight))

    # TRIMP at LTHR sustained for 1 hour:
    hrr_lthr = (lthr - rhr) / (max_hr - rhr)
    weight_lthr = 0.64 * np.exp(1.92 * hrr_lthr)
    trimp_1h = 3600.0 * hrr_lthr * weight_lthr

    return {
        "tss": trimp / trimp_1h * 100.0 if trimp_1h > 0 else 0.0,
        "trimp": trimp,
        "duration_s": int(duration_s),
    }


def hr_tss_avg(avg_hr: float, duration_s: float, lthr: float) -> dict[str, Any]:
    """Fallback hrTSS from summary heart rate.

    hrTSS = duration_h * (avg_hr / lthr)**2 * 100

    Use when only the activity summary is available (no HR stream).
    Less accurate than TRIMP-based; flag in result.
    """
    if lthr <= 0:
        raise ValueError(f"LTHR must be > 0, got {lthr}")
    duration_h = duration_s / 3600.0
    if_proxy = avg_hr / lthr
    return {
        "tss": duration_h * if_proxy**2 * 100.0,
        "method": "avg_hr",
        "duration_s": int(duration_s),
    }


def pace_tss(
    distance_m: float,
    duration_s: float,
    threshold_pace_s_per_km: float,
) -> dict[str, Any]:
    """Run TSS using flat-pace approximation.

    rTSS = duration_h * (NGS / threshold_pace)**2 * 100

    NGS (Normalised Graded Speed) needs grade-adjusted-pace from streams to
    be accurate. This function uses raw average pace as a fallback for
    summary-only activities. For per-second data, prefer a streams-aware
    `pace_tss_streams()` (not yet implemented).
    """
    if threshold_pace_s_per_km <= 0:
        raise ValueError(f"threshold_pace must be > 0, got {threshold_pace_s_per_km}")
    if distance_m <= 0 or duration_s <= 0:
        return {"tss": 0.0, "duration_s": int(duration_s), "method": "pace_avg"}

    duration_h = duration_s / 3600.0
    pace_s_per_km = duration_s / (distance_m / 1000.0)
    if_value = threshold_pace_s_per_km / pace_s_per_km  # faster pace = higher IF
    return {
        "tss": duration_h * if_value**2 * 100.0,
        "intensity_factor": if_value,
        "method": "pace_avg",
        "duration_s": int(duration_s),
    }

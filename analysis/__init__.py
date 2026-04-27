"""training-mate analysis package — pure-function math.

No I/O, no DB, no network. CLI tools under `tools/` orchestrate; this
package computes. Keeps the math testable in isolation.
"""
from analysis.tss import (
    hr_tss_avg,
    hr_tss_trimp,
    normalised_power,
    pace_tss,
    power_tss,
)

__all__ = [
    "hr_tss_avg",
    "hr_tss_trimp",
    "normalised_power",
    "pace_tss",
    "power_tss",
]

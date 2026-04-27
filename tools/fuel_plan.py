"""fuel_plan — carbs/fluids/sodium plan for a ride. Math in `docs/fueling.md`.

Args:
    --duration-h FLOAT       required (planned moving hours)
    --IF FLOAT               required (planned intensity factor)
    --temp-c FLOAT           ride temperature (optional; defaults to no hot/cold adjustment)
    --weight-kg FLOAT        override athlete_profile.weight_kg
    --heavy-sweater          add 200 mg/h sodium

Output: see docs/fueling.md "What `fuel_plan.py` returns".
"""
from __future__ import annotations

import argparse
import sys

from _common import athlete_profile, emit, fail  # type: ignore[import-not-found]
from analysis.fueling import plan


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--duration-h", type=float, required=True)
    p.add_argument("--IF", dest="intensity_factor", type=float, required=True)
    p.add_argument("--temp-c", type=float, default=None)
    p.add_argument("--weight-kg", type=float, default=None)
    p.add_argument("--heavy-sweater", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str]) -> None:
    args = _parse_args(argv)
    profile = athlete_profile()
    weight = args.weight_kg or float(profile.get("weight_kg") or 75.0)
    if args.duration_h <= 0:
        fail("--duration-h must be > 0")
    if not 0.3 <= args.intensity_factor <= 1.5:
        fail("--IF should be in 0.3..1.5")
    out = plan(
        duration_h=args.duration_h,
        intensity_factor=args.intensity_factor,
        temp_c=args.temp_c,
        weight_kg=weight,
        heavy_sweater=args.heavy_sweater,
    )
    if profile.get("placeholders_used") and "weight_kg" in profile["placeholders_used"]:
        out["weight_placeholder"] = True
    emit(out)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        fail(str(e))

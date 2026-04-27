"""generate_workout — produce a structured workout.

Args:
    --kind {endurance,recovery,sst,threshold,vo2,race}    required
    --duration-min N           for endurance/recovery/race (ignored for SST/Thr/VO2)
    --template STR             for SST: 2x20|3x15|4x10
                               for threshold: 2x20|3x15|4x10|overunders
                               for VO2: 5x4|4x4_norwegian|6x3|30_15
    --name STR                 optional title for the .zwo / event description

Output:
    {
      "kind": "...",
      "name": "...",
      "duration_min": int,
      "estimated_tss": float,
      "structure": [{kind, duration_s, power_lo, power_hi, note?}, ...],
      "zwo_path_hint": "tools/export_workout.py emits the file"
    }
"""
from __future__ import annotations

import argparse
import sys

from _common import emit, fail  # type: ignore[import-not-found]
from analysis.workouts import build_workout, estimate_tss


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--kind", required=True)
    p.add_argument("--duration-min", type=int, default=None)
    p.add_argument("--template", default=None)
    p.add_argument("--name", default=None)
    return p.parse_args(argv)


def main(argv: list[str]) -> None:
    args = _parse_args(argv)
    try:
        steps = build_workout(args.kind, args.duration_min, args.template)
    except ValueError as e:
        fail(str(e))

    total_s = sum(s["duration_s"] for s in steps)
    name = args.name or f"{args.kind.upper()}{(' ' + args.template) if args.template else ''} {total_s // 60}min"
    emit(
        {
            "kind": args.kind,
            "template": args.template,
            "name": name,
            "duration_min": total_s // 60,
            "estimated_tss": estimate_tss(steps),
            "structure": steps,
            "zwo_path_hint": "use tools/export_workout.py to write a .zwo file",
        }
    )


if __name__ == "__main__":
    main(sys.argv[1:])

"""Workout templates — structured intervals for each session kind.

Source of truth is `docs/workout-library.md`. This module gives
`tools/generate_workout.py` typed structures it can serialize to
`workouts.structure_json` or to `.zwo` XML.

Each step is `{kind, duration_s, power_lo, power_hi, cadence_target?, note?}`
where `power_lo`/`power_hi` are FTP fractions (0.0–2.0).
"""
from __future__ import annotations

from typing import Any

# kind → list of (label, picker_fn)
ENDURANCE_KINDS = {"endurance", "z2"}
RECOVERY_KINDS = {"recovery", "z1"}
SST_KINDS = {"sst", "sweet_spot", "sweetspot"}
THRESHOLD_KINDS = {"threshold", "z4"}
VO2_KINDS = {"vo2", "vo2max", "z5"}


def _warmup(seconds: int = 600) -> dict[str, Any]:
    return {
        "kind": "warmup",
        "duration_s": seconds,
        "power_lo": 0.45,
        "power_hi": 0.65,
        "note": "easy spin → light surges",
    }


def _cooldown(seconds: int = 300) -> dict[str, Any]:
    return {
        "kind": "cooldown",
        "duration_s": seconds,
        "power_lo": 0.55,
        "power_hi": 0.40,
        "note": "easy spin",
    }


def _steady(seconds: int, power: float, **kw: Any) -> dict[str, Any]:
    return {"kind": "steady", "duration_s": seconds, "power_lo": power, "power_hi": power, **kw}


def _interval(seconds: int, power: float, label: str = "interval") -> dict[str, Any]:
    return {"kind": label, "duration_s": seconds, "power_lo": power, "power_hi": power}


def _rest(seconds: int) -> dict[str, Any]:
    return {"kind": "rest", "duration_s": seconds, "power_lo": 0.55, "power_hi": 0.55}


def endurance_z2(duration_min: int) -> list[dict[str, Any]]:
    """Steady Z2 with optional 30-s spin-ups every 15 min."""
    main_min = duration_min - 15  # 10 min warmup, 5 min cooldown
    if main_min < 30:
        main_min = max(30, duration_min - 10)
    return [
        _warmup(600),
        _steady(main_min * 60, 0.68, note="endurance Z2; throw 5×30s 90-rpm spin-ups every 15 min"),
        _cooldown(300),
    ]


def recovery_z1(duration_min: int) -> list[dict[str, Any]]:
    """Pure Z1 spin."""
    return [
        _warmup(300),
        _steady((duration_min - 10) * 60, 0.50, note="recovery Z1; RPE ≤ 3"),
        _cooldown(300),
    ]


def sst(template: str = "2x20") -> list[dict[str, Any]]:
    """Sweet spot. Templates: '2x20', '3x15', '4x10'."""
    plans = {
        "2x20": [(1200, 0.90, 300)],  # 2 reps of (20 min @ 0.90, rec 5 min)
        "3x15": [(900, 0.91, 240)],   # 3 reps × (15 min @ 0.91, rec 4 min)
        "4x10": [(600, 0.93, 180)],   # 4 reps × (10 min @ 0.93, rec 3 min)
    }
    if template not in plans:
        template = "2x20"
    work_s, power, rec_s = plans[template][0]
    reps = {"2x20": 2, "3x15": 3, "4x10": 4}[template]
    body: list[dict[str, Any]] = []
    for _ in range(reps):
        body.append(_interval(work_s, power, "sst"))
        body.append(_rest(rec_s))
    return [_warmup(900), *body, _cooldown(600)]


def threshold(template: str = "2x20") -> list[dict[str, Any]]:
    """Threshold. Templates: '2x20', '3x15', '4x10', 'overunders'."""
    if template == "overunders":
        # 6×3min sets of (30s @ 1.05 / 30s @ 0.95), 3 min Z2 between sets
        body: list[dict[str, Any]] = []
        for _set in range(6):
            for _ in range(3):
                body.append(_interval(30, 1.05, "over"))
                body.append(_interval(30, 0.95, "under"))
            body.append(_rest(180))
        return [_warmup(900), *body, _cooldown(600)]

    plans = {
        "2x20": (1200, 0.98, 300, 2),
        "3x15": (900, 1.00, 300, 3),
        "4x10": (600, 1.02, 240, 4),
    }
    if template not in plans:
        template = "2x20"
    work_s, power, rec_s, reps = plans[template]
    body = []
    for _ in range(reps):
        body.append(_interval(work_s, power, "threshold"))
        body.append(_rest(rec_s))
    return [_warmup(900), *body, _cooldown(600)]


def vo2max(template: str = "5x4") -> list[dict[str, Any]]:
    """VO2max. Templates: '5x4', '4x4_norwegian', '6x3', '30_15'."""
    if template == "30_15":
        # 13 reps of 30/15 = 9:45 work; do 3 sets with 4 min Z2 between
        body: list[dict[str, Any]] = []
        for _set in range(3):
            for _ in range(13):
                body.append(_interval(30, 1.20, "vo2"))
                body.append(_interval(15, 0.60, "rec"))
            body.append(_rest(240))
        return [_warmup(900), *body, _cooldown(600)]

    plans = {
        "5x4":         (240, 1.12, 240, 5),
        "4x4_norwegian": (240, 1.15, 180, 4),
        "6x3":         (180, 1.17, 180, 6),
    }
    if template not in plans:
        template = "5x4"
    work_s, power, rec_s, reps = plans[template]
    body = []
    for _ in range(reps):
        body.append(_interval(work_s, power, "vo2"))
        body.append(_rest(rec_s))
    return [_warmup(900), *body, _cooldown(600)]


def race_event(duration_min: int) -> list[dict[str, Any]]:
    """Generic race-pace placeholder — variable zone, mostly self-paced."""
    return [
        _warmup(600),
        _steady((duration_min - 15) * 60, 0.85, note="race-pace; variable per course"),
        _cooldown(300),
    ]


KIND_BUILDERS = {
    **{k: lambda d=180, t=None: endurance_z2(d) for k in ENDURANCE_KINDS},
    **{k: lambda d=45, t=None: recovery_z1(d) for k in RECOVERY_KINDS},
    **{k: lambda d=None, t="2x20": sst(t or "2x20") for k in SST_KINDS},
    **{k: lambda d=None, t="2x20": threshold(t or "2x20") for k in THRESHOLD_KINDS},
    **{k: lambda d=None, t="5x4": vo2max(t or "5x4") for k in VO2_KINDS},
    "race": lambda d=180, t=None: race_event(d),
}


def build_workout(kind: str, duration_min: int | None = None, template: str | None = None) -> list[dict[str, Any]]:
    """Top-level builder. Returns list[step] for the given kind + template."""
    kind = kind.lower().strip()
    builder = KIND_BUILDERS.get(kind)
    if builder is None:
        raise ValueError(
            f"unknown workout kind '{kind}'. "
            f"Try one of: endurance, recovery, sst, threshold, vo2, race."
        )
    if kind in ENDURANCE_KINDS or kind in RECOVERY_KINDS or kind == "race":
        return builder(duration_min or 90, None)
    return builder(None, template)


def estimate_tss(steps: list[dict[str, Any]]) -> float:
    """Quick TSS estimate from steps. Treats power_lo as average for steady steps,
    midpoint for ranges. Coggan: TSS = duration_h × IF² × 100."""
    total_tss = 0.0
    for s in steps:
        avg_power = (s["power_lo"] + s["power_hi"]) / 2
        h = s["duration_s"] / 3600
        total_tss += h * avg_power**2 * 100
    return round(total_tss, 1)


def to_zwo(steps: list[dict[str, Any]], name: str, description: str = "") -> str:
    """Render a Zwift workout XML (.zwo) string."""
    rows: list[str] = []
    for s in steps:
        kind = s["kind"]
        dur = int(s["duration_s"])
        plo = s["power_lo"]
        phi = s["power_hi"]
        if kind == "warmup":
            rows.append(f'    <Warmup Duration="{dur}" PowerLow="{plo}" PowerHigh="{phi}"/>')
        elif kind == "cooldown":
            rows.append(f'    <Cooldown Duration="{dur}" PowerLow="{plo}" PowerHigh="{phi}"/>')
        else:
            rows.append(f'    <SteadyState Duration="{dur}" Power="{plo}"/>')
    body = "\n".join(rows)
    return (
        '<workout_file>\n'
        f'  <author>Training-Mate</author>\n'
        f'  <name>{name}</name>\n'
        f'  <description>{description}</description>\n'
        '  <sportType>bike</sportType>\n'
        '  <workout>\n'
        f'{body}\n'
        '  </workout>\n'
        '</workout_file>\n'
    )

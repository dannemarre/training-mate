"""plan_week — propose a 7-day plan and write journal/YYYY-WW-plan.md.

Args:
    --week-start YYYY-MM-DD    must be a Monday; default: next Monday
    --mode {pyramidal,polarized,recovery,auto}   default: auto (chooses from form_state)
    --no-write                 just print the proposed plan; don't touch the journal

Output:
    {
      "week_start": "YYYY-MM-DD",
      "mode": "...",
      "form_at_start": {...},
      "tss_total": float,
      "tss_budget": [low, high],
      "within_budget": bool,
      "plan": [{date, weekday, session, kind, duration_min, target_tss, source, notes}],
      "journal_path": "journal/YYYY-WW-plan.md" | null
    }

This is the *proposal*. The /plan-week skill (and the `coach` subagent)
review it, adjust based on knee status / wellness / race calendar, then
ask Martin for confirmation before writing.

The default week skeleton comes from docs/group-rides.md (Sunday Ängby
söndag anchor, Wednesday Onsdagsgrus, Tue/Thu mid-week intensity).
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

from _common import REPO_ROOT, emit, fail, log, open_db  # type: ignore[import-not-found]
from analysis.pmc import form_state
from analysis.workouts import build_workout, estimate_tss

# Per docs/training-science.md "TSS budget per week (rough)":
TSS_BUDGET = {
    "detrained":  (200, 400),
    "race-ready": (400, 600),
    "neutral":    (450, 700),
    "productive": (500, 800),
    "overreached": (300, 500),
    "risky":      (200, 400),
    "crashing":   (100, 250),
}


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--week-start", help="YYYY-MM-DD; must be a Monday")
    p.add_argument("--mode", choices=["pyramidal", "polarized", "recovery", "auto"], default="auto")
    p.add_argument("--no-write", action="store_true")
    return p.parse_args(argv)


def _next_monday(today: dt.date) -> dt.date:
    days = (7 - today.weekday()) % 7
    if days == 0:
        days = 7  # always pick the *next* Monday
    return today + dt.timedelta(days=days)


def _form_at(date: dt.date) -> dict | None:
    with open_db() as conn:
        row = conn.execute(
            "SELECT date, ctl, atl, tsb FROM pmc_daily WHERE date <= ? "
            "ORDER BY date DESC LIMIT 1",
            (date.isoformat(),),
        ).fetchone()
        if row is None:
            return None
        seven_days_before = (date - dt.timedelta(days=7)).isoformat()
        earlier = conn.execute(
            "SELECT ctl FROM pmc_daily WHERE date <= ? ORDER BY date DESC LIMIT 1",
            (seven_days_before,),
        ).fetchone()
    ramp = float(row["ctl"]) - float(earlier["ctl"]) if earlier else None
    return {
        "as_of": row["date"],
        "ctl": round(float(row["ctl"]), 2),
        "atl": round(float(row["atl"]), 2),
        "tsb": round(float(row["tsb"]), 2),
        "ramp_7d": round(ramp, 2) if ramp is not None else None,
        "form_state": form_state(float(row["tsb"]), ramp),
    }


def _choose_mode(form: dict | None) -> str:
    if form is None:
        return "pyramidal"  # safe default
    if form["form_state"] in ("crashing", "risky"):
        return "recovery"
    if form["form_state"] == "overreached":
        return "recovery"
    return "pyramidal"  # polarized only kicks in pre-A-race; defer to subagent


def _build_session(kind: str, duration_min: int | None = None, template: str | None = None) -> dict:
    """Build a session row with an estimated TSS."""
    steps = build_workout(kind, duration_min, template)
    total_s = sum(s["duration_s"] for s in steps)
    return {
        "kind": kind,
        "template": template,
        "duration_min": total_s // 60,
        "target_tss": estimate_tss(steps),
        "structure": steps,
    }


def _skeleton_pyramidal() -> dict[str, dict | None]:
    """Mon..Sun skeleton for a build/pyramidal week."""
    return {
        "Mon": {"name": "Rest + knee rehab", "kind": "rest_rehab", "duration_min": 25,
                "target_tss": 0,
                "notes": "Activation + B-list rehab (TKE band, Spanish squat, step-up); see docs/knee-rehab.md."},
        "Tue": {**_build_session("sst", template="3x15"),
                "name": "SST 3×15 @ 90-92% FTP",
                "notes": "Mid-week intensity. Cadence ≥85 rpm; stop set if knee creeps."},
        "Wed": {**_build_session("endurance", duration_min=90),
                "name": "Onsdagsgrus (Z2 gravel) — or solo Z2 90 min",
                "notes": "If group's hot, drop to solo Z2; per CLAUDE.md rule #3 the social ride is a slot, not a target."},
        "Thu": {**_build_session("threshold", template="2x20"),
                "name": "Threshold 2×20 @ 95-100% FTP",
                "notes": "Drop to 4×10 if Tuesday left legs heavy; threshold for cyclists per docs/workout-library.md."},
        "Fri": {"name": "Rest + knee rehab + light strength", "kind": "rest_rehab",
                "duration_min": 25, "target_tss": 0,
                "notes": "Pre-rest day. B-list rehab; light strength on the gym-at-work."},
        "Sat": {**_build_session("recovery", duration_min=60),
                "name": "Pre-Sunday activation (Z1/Z2 60 min)",
                "notes": "Easy spin; throw 3×30s spin-ups in last 15 min for activation."},
        "Sun": {**_build_session("endurance", duration_min=180),
                "name": "Ängby söndag 07:30 (long Z2)",
                "notes": "Week's anchor. Pyramidal-classified as endurance even with Z4 surges (per docs/training-distribution.md)."},
    }


def _skeleton_recovery() -> dict[str, dict | None]:
    """Recovery week — no Z4+, scaled volume."""
    return {
        "Mon": {"name": "Rest + full rehab block", "kind": "rest_rehab", "duration_min": 30, "target_tss": 0,
                "notes": "Full B-list rehab session. No bike."},
        "Tue": {**_build_session("recovery", duration_min=60),
                "name": "Recovery Z1 60 min",
                "notes": "Z1 only; RPE ≤3. Skip if HRV in breach for ≥3 days."},
        "Wed": {"name": "Rest", "kind": "rest", "duration_min": 0, "target_tss": 0,
                "notes": "Skip Onsdagsgrus this week — group's pace will undo recovery."},
        "Thu": {**_build_session("endurance", duration_min=60),
                "name": "Easy Z2 60 min",
                "notes": "Floor of Z2 (60-65% FTP)."},
        "Fri": {"name": "Rest + knee rehab", "kind": "rest_rehab", "duration_min": 20, "target_tss": 0,
                "notes": "Light rehab. No strength."},
        "Sat": {**_build_session("recovery", duration_min=45),
                "name": "Recovery spin 45 min",
                "notes": "Movement, no load."},
        "Sun": {**_build_session("endurance", duration_min=120),
                "name": "Ängby söndag — back of the group, social pace",
                "notes": "Skip the surges. If form is crashing/risky, swap for solo 90 min Z2."},
    }


def _build_plan(week_start: dt.date, mode: str) -> list[dict]:
    skeleton = _skeleton_recovery() if mode == "recovery" else _skeleton_pyramidal()
    plan: list[dict] = []
    for i, weekday in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
        date = week_start + dt.timedelta(days=i)
        day = skeleton[weekday]
        # Drop heavy `structure` from the row to keep the plan compact;
        # /plan-week can re-derive it via generate_workout.py for export.
        compact = {k: v for k, v in (day or {}).items() if k != "structure"}
        plan.append({"date": date.isoformat(), "weekday": weekday, **compact})
    return plan


def _render_journal_md(week_start: dt.date, mode: str, form: dict | None, plan: list[dict], total_tss: float, budget: tuple[int, int]) -> str:
    iso_year, iso_week, _ = week_start.isocalendar()
    lines: list[str] = [
        f"# Week {iso_year}-W{iso_week:02d} plan",
        "",
        f"- **Week start**: {week_start.isoformat()} (Monday, Europe/Stockholm)",
        f"- **Mode**: {mode}",
    ]
    if form:
        lines.append(
            f"- **Form at start**: CTL {form['ctl']:.0f} / ATL {form['atl']:.0f} / "
            f"TSB {form['tsb']:+.0f} / ramp_7d {form['ramp_7d']:+.1f if form['ramp_7d'] is not None else 'n/a'} → "
            f"**{form['form_state']}**"
        )
    lines += [
        f"- **Estimated weekly TSS**: {total_tss:.0f} (budget: {budget[0]}–{budget[1]} per docs/training-science.md)",
        "",
        "## Daily plan",
        "",
        "| Day | Date | Session | Duration | TSS |",
        "|---|---|---|---|---|",
    ]
    for d in plan:
        name = d.get("name", "—")
        dur = d.get("duration_min") or 0
        tss = d.get("target_tss") or 0
        lines.append(
            f"| {d['weekday']} | {d['date']} | {name} | {dur} min | {tss:.0f} |"
        )
    lines += [
        "",
        "## Notes",
        "",
    ]
    for d in plan:
        if d.get("notes"):
            lines.append(f"- **{d['weekday']}**: {d['notes']}")
    lines += [
        "",
        "## Calendar",
        "",
        "*Not yet upserted. Use `/plan-week` skill, confirm the diff, then run `tools/calendar_upsert_week.py`.*",
        "",
        "## Open questions",
        "",
        "- Knee status this week (0-10)?",
        "- Travel / commitments outside Calendar?",
        "- Race-week or normal build week?",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> None:
    args = _parse_args(argv)
    today = dt.date.today()

    if args.week_start:
        week_start = dt.date.fromisoformat(args.week_start)
        if week_start.weekday() != 0:
            fail(f"--week-start must be a Monday; {week_start} is {week_start.strftime('%A')}")
    else:
        week_start = _next_monday(today)

    form = _form_at(week_start)
    mode = _choose_mode(form) if args.mode == "auto" else args.mode

    plan = _build_plan(week_start, mode)
    total_tss = sum((d.get("target_tss") or 0) for d in plan)

    state_for_budget = form["form_state"] if form else "neutral"
    budget = TSS_BUDGET.get(state_for_budget, (450, 700))
    within = budget[0] <= total_tss <= budget[1]

    journal_path = None
    if not args.no_write:
        iso_year, iso_week, _ = week_start.isocalendar()
        journal_path = REPO_ROOT / "journal" / f"{iso_year}-{iso_week:02d}-plan.md"
        if journal_path.exists():
            log(f"[plan-week] {journal_path} exists — appending '-revB' instead")
            journal_path = journal_path.with_name(journal_path.stem + "-revB.md")
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_path.write_text(_render_journal_md(week_start, mode, form, plan, total_tss, budget))

    emit(
        {
            "week_start": week_start.isoformat(),
            "mode": mode,
            "form_at_start": form,
            "tss_total": round(total_tss, 1),
            "tss_budget": list(budget),
            "within_budget": within,
            "plan": plan,
            "journal_path": str(journal_path) if journal_path else None,
        }
    )


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        fail(str(e))

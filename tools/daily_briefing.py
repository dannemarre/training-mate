"""daily_briefing — aggregate today's form, wellness, plan, knee, and group rides.

Args:
    --date YYYY-MM-DD   default: today (Europe/Stockholm)

Output: a single JSON object (see schema below). The /today skill consumes
this and renders a 5-bullet briefing for Martin.

This tool deliberately does NOT prescribe a session — it surfaces signals.
The /today and /plan-week skills (and the coach subagent) do the prescribing.

Schema:
{
  "date": "YYYY-MM-DD",
  "weekday": "Monday",
  "form":     {ctl, atl, tsb, ramp_7d, form_state, ramp_warning, ramp_critical, citation},
  "wellness": {hrv: {state, breach_days, baseline_7d, swc, today},
               sleep: {state, note, minutes},
               rhr: {flag, delta, baseline}},
  "today_session":   {parsed from journal/YYYY-WW-plan.md if present, else null},
  "group_rides":     [list of today's regular rides from docs/group-rides.md],
  "knee_alert":      "green" | "yellow" | "red" | "unknown",
  "knee_recent":     "free-text snippet from last 3 days' journal",
  "advisory":        ["short bullets the agent should surface"]
}
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
import zoneinfo
from pathlib import Path

from _common import REPO_ROOT, emit, fail, open_db  # type: ignore[import-not-found]
from analysis.pmc import form_state
from analysis.wellness import hrv_state, rhr_drift, sleep_advisory

LOCAL_TZ = zoneinfo.ZoneInfo("Europe/Stockholm")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--date", help="YYYY-MM-DD; default today")
    return p.parse_args(argv)


# ---- form ------------------------------------------------------------------


def _form_block(today: dt.date) -> dict | None:
    with open_db() as conn:
        latest = conn.execute(
            "SELECT date, ctl, atl, tsb FROM pmc_daily WHERE date <= ? "
            "ORDER BY date DESC LIMIT 1",
            (today.isoformat(),),
        ).fetchone()
        if latest is None:
            return None
        seven_days_ago = (today - dt.timedelta(days=7)).isoformat()
        earlier = conn.execute(
            "SELECT ctl FROM pmc_daily WHERE date <= ? ORDER BY date DESC LIMIT 1",
            (seven_days_ago,),
        ).fetchone()
    ramp = float(latest["ctl"]) - float(earlier["ctl"]) if earlier else None
    return {
        "as_of": latest["date"],
        "ctl": round(float(latest["ctl"]), 2),
        "atl": round(float(latest["atl"]), 2),
        "tsb": round(float(latest["tsb"]), 2),
        "ramp_7d": round(ramp, 2) if ramp is not None else None,
        "form_state": form_state(float(latest["tsb"]), ramp),
        "ramp_warning": ramp is not None and ramp > 8.0,
        "ramp_critical": ramp is not None and ramp > 10.0,
        "citation": "docs/training-science.md#tsb-interpretation-thresholds",
    }


# ---- wellness --------------------------------------------------------------


def _wellness_block(today: dt.date) -> dict:
    with open_db() as conn:
        rows = conn.execute(
            "SELECT date, hrv_ms, sleep_minutes, resting_hr "
            "FROM wellness_daily WHERE date <= ? "
            "ORDER BY date DESC LIMIT 14",
            (today.isoformat(),),
        ).fetchall()

    if not rows:
        return {
            "hrv": {"state": "no_baseline", "note": "wellness_daily empty — run sync --include-wellness"},
            "sleep": {"state": "unknown", "note": "no sleep data"},
            "rhr": {"flag": False, "delta": None, "baseline": None},
        }

    today_row = rows[0]
    history_rows = rows[1:8]  # next 7 most recent days, EXCLUDING today
    hrv_history = [r["hrv_ms"] for r in history_rows if r["hrv_ms"] is not None]
    rhr_history = [r["resting_hr"] for r in history_rows if r["resting_hr"] is not None]

    hrv = hrv_state(today_row["hrv_ms"], hrv_history)
    prior_sleep = history_rows[0]["sleep_minutes"] if history_rows else None
    sleep = sleep_advisory(today_row["sleep_minutes"], prior_night_minutes=prior_sleep)
    rhr = rhr_drift(today_row["resting_hr"], rhr_history)

    return {
        "hrv": {
            "state": hrv.state,
            "breach_days": hrv.breach_days,
            "baseline_7d": round(hrv.baseline_7d, 1) if hrv.baseline_7d is not None else None,
            "swc": round(hrv.swc, 2) if hrv.swc is not None else None,
            "today": hrv.today,
        },
        "sleep": {**sleep, "minutes": today_row["sleep_minutes"]},
        "rhr": rhr,
    }


# ---- planned session -------------------------------------------------------


def _planned_session(today: dt.date) -> dict | None:
    """Parse journal/YYYY-WW-plan.md for today's row.

    The template uses a markdown table. We look for a line whose first
    non-empty cell starts with the local weekday name or YYYY-MM-DD.
    """
    iso_year, iso_week, _ = today.isocalendar()
    plan_path = REPO_ROOT / "journal" / f"{iso_year}-{iso_week:02d}-plan.md"
    if not plan_path.exists():
        return None

    weekday = today.strftime("%A")
    iso_str = today.isoformat()
    content = plan_path.read_text(encoding="utf-8")

    for line in content.splitlines():
        # Match either "| Mon 2026-04-27 | …" or "| 2026-04-27 | …"
        if line.lstrip().startswith("|"):
            cells = [c.strip() for c in line.split("|")[1:-1]]
            first = cells[0] if cells else ""
            if iso_str in first or first.startswith(weekday[:3]):
                return {"path": str(plan_path), "row": cells}
    return {"path": str(plan_path), "row": None}


# ---- group rides -----------------------------------------------------------


def _group_rides_today(weekday: str) -> list[dict]:
    """Quick map from weekday → today's known regular rides.

    Source-of-truth is docs/group-rides.md; this is just a parsed shortcut.
    """
    rides = []
    if weekday == "Sunday":
        rides.append({"name": "Ängby söndag", "start_local": "07:30", "type": "harder training, longer", "anchor": True})
    if weekday == "Wednesday":
        rides.append({"name": "Onsdagsgrus", "start_local": "18:00", "type": "Z2/Z3 gravel"})
    if weekday in ("Tuesday", "Thursday"):
        rides.append({"name": "CK Valhall (Tue/Thu options)", "start_local": "evening", "type": "varies"})
    return rides


# ---- knee --------------------------------------------------------------------


def _knee_status(today: dt.date) -> tuple[str, str | None]:
    """Read journal/YYYY-WW-log.md for the current and prior week.

    Look for `Knee` mentions with a 0-10 score in the last 3 days.
    Map: 0-1=green, 2-3=yellow, 4+=red. unknown if no recent data.
    """
    candidate_paths: list[Path] = []
    for offset in range(0, 8):
        d = today - dt.timedelta(days=offset)
        iso_year, iso_week, _ = d.isocalendar()
        candidate_paths.append(REPO_ROOT / "journal" / f"{iso_year}-{iso_week:02d}-log.md")
    seen = set()
    paths = [p for p in candidate_paths if p not in seen and not seen.add(p)]

    most_recent_score: int | None = None
    most_recent_snippet: str | None = None
    score_pattern = re.compile(r"\b(?:knee|smärta|score)\D*(\d+)\s*/?\s*10", re.IGNORECASE)

    for path in paths:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        # Walk by day section, looking for "knee" lines
        for section in re.split(r"^##\s+", text, flags=re.MULTILINE):
            if "knee" not in section.lower():
                continue
            m = score_pattern.search(section)
            if m:
                most_recent_score = int(m.group(1))
                # Snippet: the 'knee' line itself
                for line in section.splitlines():
                    if "knee" in line.lower() and m.group(0) in line.lower():
                        most_recent_snippet = line.strip()
                        break
                break
        if most_recent_score is not None:
            break

    if most_recent_score is None:
        return ("unknown", None)
    if most_recent_score <= 1:
        return ("green", most_recent_snippet)
    if most_recent_score <= 3:
        return ("yellow", most_recent_snippet)
    return ("red", most_recent_snippet)


# ---- advisory --------------------------------------------------------------


def _advisory(form: dict | None, wellness: dict, knee: str) -> list[str]:
    """Concatenate the headline signals into short bullets the agent will say first."""
    out: list[str] = []
    if form:
        if form["ramp_critical"]:
            out.append(f"🚨 7-day CTL ramp +{form['ramp_7d']:.1f} — crash territory; recovery week now")
        elif form["ramp_warning"]:
            out.append(f"⚠️ 7-day CTL ramp +{form['ramp_7d']:.1f} — at warning ceiling; don't add load this week")
        out.append(f"Form: {form['form_state']} (TSB {form['tsb']:+.0f})")
    hrv = wellness.get("hrv", {})
    if hrv.get("state") == "recovery_required":
        out.append(f"🚨 HRV: {hrv['breach_days']} consecutive breaches → recovery only")
    elif hrv.get("state") == "easy_only":
        out.append(f"⚠️ HRV: {hrv['breach_days']} consecutive breaches → easy only today")
    elif hrv.get("state") == "swap_hard_for_z2":
        out.append(f"⚠️ HRV: 2 consecutive breaches → swap any planned hard session for Z2")
    sleep = wellness.get("sleep", {})
    if sleep.get("state") in ("recovery_only", "easy_only", "no_z4_plus"):
        out.append(f"😴 Sleep: {sleep['note']}")
    if knee == "red":
        out.append("🚨 Knee red — skip planned hard session, switch to rehab + Z2 only")
    elif knee == "yellow":
        out.append("⚠️ Knee yellow — drop intensity / cadence ≥80 rpm, consider rehab session")
    return out


# ---- main ------------------------------------------------------------------


def main(argv: list[str]) -> None:
    args = _parse_args(argv)
    today = (
        dt.date.fromisoformat(args.date)
        if args.date
        else dt.datetime.now(LOCAL_TZ).date()
    )

    form = _form_block(today)
    wellness = _wellness_block(today)
    plan = _planned_session(today)
    rides = _group_rides_today(today.strftime("%A"))
    knee, knee_snippet = _knee_status(today)

    out = {
        "date": today.isoformat(),
        "weekday": today.strftime("%A"),
        "form": form,
        "wellness": wellness,
        "today_session": plan,
        "group_rides": rides,
        "knee_alert": knee,
        "knee_recent": knee_snippet,
        "advisory": _advisory(form, wellness, knee),
    }
    emit(out)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        fail(str(e))

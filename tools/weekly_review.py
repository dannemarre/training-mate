"""weekly_review — diff plan vs actual for a given ISO week.

Args:
    --week YYYY-WW    optional; default: last completed week (ISO)

Output:
    {
      "week": "YYYY-WW",
      "week_start": "YYYY-MM-DD",  # Monday
      "week_end":   "YYYY-MM-DD",  # Sunday
      "plan_path": "...",
      "log_path": "...",
      "tss": {"planned": float, "actual": float},
      "form": {"start": {...}, "end": {...}, "ramp_7d": float},
      "by_day": [{date, weekday, planned: {...}, actual: [{...}], moved: bool, missed: bool}],
      "session_distribution": {"endurance": N, "intensity": M, "recovery": K, "rest": L},
      "summary": "..."
    }

The /review skill (and `weekly-reviewer` subagent) consume this and add
qualitative analysis grounded in `docs/training-distribution.md`.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
import zoneinfo
from pathlib import Path

from _common import REPO_ROOT, emit, fail, open_db  # type: ignore[import-not-found]

LOCAL_TZ = zoneinfo.ZoneInfo("Europe/Stockholm")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--week", help="YYYY-WW; default last completed week")
    return p.parse_args(argv)


def _last_complete_week(today: dt.date) -> tuple[int, int]:
    """ISO year, ISO week of the most recently *completed* week."""
    # If today is Monday, last week ends yesterday; if today is Sunday, last week ended last Sunday
    days_since_sunday = (today.weekday() + 1) % 7  # Monday=0 → 1, …, Sunday=6 → 0
    last_sunday = today - dt.timedelta(days=days_since_sunday + 1)
    iso_year, iso_week, _ = last_sunday.isocalendar()
    return iso_year, iso_week


def _week_dates(iso_year: int, iso_week: int) -> tuple[dt.date, dt.date]:
    monday = dt.date.fromisocalendar(iso_year, iso_week, 1)
    sunday = dt.date.fromisocalendar(iso_year, iso_week, 7)
    return monday, sunday


def _parse_plan(plan_path: Path) -> dict[str, dict]:
    """Map weekday→planned row from journal/YYYY-WW-plan.md table."""
    if not plan_path.exists():
        return {}
    out: dict[str, dict] = {}
    text = plan_path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) < 5:
            continue
        # Expect "| Mon | YYYY-MM-DD | Session | XX min | NN |"
        if not re.match(r"[A-Z][a-z]+", cells[0]):
            continue
        weekday = cells[0]
        date = cells[1]
        if not re.match(r"\d{4}-\d{2}-\d{2}", date):
            continue
        out[weekday] = {
            "weekday": weekday,
            "date": date,
            "session": cells[2],
            "duration_min": cells[3],
            "target_tss": cells[4],
        }
    return out


def _local_date(iso_utc: str) -> dt.date:
    s = iso_utc.replace("Z", "+00:00")
    if "+" not in s and "-" not in s[10:]:
        s = s + "+00:00"
    return dt.datetime.fromisoformat(s).astimezone(LOCAL_TZ).date()


def _classify_session(act: dict, ftp: float | None) -> str:
    """Seiler-style session classification by % time in Z1/Z2 (rough proxy
    using avg power vs FTP because we don't decompose streams here)."""
    if act.get("avg_power") and ftp:
        ratio = act["avg_power"] / ftp
        if ratio < 0.76:
            return "endurance"
        if ratio < 0.91:
            return "tempo"
        if ratio < 1.06:
            return "threshold"
        return "vo2"
    if act.get("tss_kind") == "hr" and act.get("avg_hr"):
        # Without LTHR readily available, rough thresholds via avg HR
        return "endurance" if act["avg_hr"] < 145 else "tempo_or_intensity"
    return "unknown"


def main(argv: list[str]) -> None:
    args = _parse_args(argv)
    today = dt.datetime.now(LOCAL_TZ).date()

    if args.week:
        m = re.match(r"(\d{4})-(\d{1,2})", args.week)
        if not m:
            fail("--week must be YYYY-WW")
        iso_year, iso_week = int(m.group(1)), int(m.group(2))
    else:
        iso_year, iso_week = _last_complete_week(today)

    monday, sunday = _week_dates(iso_year, iso_week)
    plan_path = REPO_ROOT / "journal" / f"{iso_year}-{iso_week:02d}-plan.md"
    log_path = REPO_ROOT / "journal" / f"{iso_year}-{iso_week:02d}-log.md"
    plan = _parse_plan(plan_path)

    with open_db() as conn:
        ftp_row = conn.execute(
            "SELECT ftp_w FROM athlete_profile WHERE id = 1"
        ).fetchone()
        ftp = float(ftp_row["ftp_w"]) if ftp_row and ftp_row["ftp_w"] else None

        from_dt = dt.datetime.combine(monday, dt.time.min, tzinfo=LOCAL_TZ).astimezone(dt.timezone.utc).isoformat()
        to_dt = dt.datetime.combine(sunday + dt.timedelta(days=1), dt.time.min, tzinfo=LOCAL_TZ).astimezone(dt.timezone.utc).isoformat()
        acts = conn.execute(
            "SELECT id, source, start_utc, sport, duration_s, distance_m, "
            "avg_power, np, intensity_factor, tss, tss_kind, avg_hr "
            "FROM activities WHERE start_utc >= ? AND start_utc < ? "
            "ORDER BY start_utc",
            (from_dt, to_dt),
        ).fetchall()

        form_start = conn.execute(
            "SELECT date, ctl, atl, tsb FROM pmc_daily WHERE date <= ? "
            "ORDER BY date DESC LIMIT 1",
            ((monday - dt.timedelta(days=1)).isoformat(),),
        ).fetchone()
        form_end = conn.execute(
            "SELECT date, ctl, atl, tsb FROM pmc_daily WHERE date <= ? "
            "ORDER BY date DESC LIMIT 1",
            (sunday.isoformat(),),
        ).fetchone()

    by_day_acts: dict[str, list[dict]] = {}
    for a in acts:
        d = _local_date(a["start_utc"])
        by_day_acts.setdefault(d.isoformat(), []).append(dict(a))

    actual_total_tss = 0.0
    by_day_out = []
    distribution: dict[str, int] = {}
    for i in range(7):
        d = monday + dt.timedelta(days=i)
        weekday = d.strftime("%A")[:3]  # Mon/Tue/...
        planned = plan.get(weekday)
        actual = by_day_acts.get(d.isoformat(), [])
        for a in actual:
            actual_total_tss += float(a.get("tss") or 0.0)
            cls = _classify_session(a, ftp)
            distribution[cls] = distribution.get(cls, 0) + 1
        # Detect "rest" from planned → 0 TSS but actual ride happened: "added"
        # Detect "planned hard" but actual zero/easy: "missed"
        moved = False
        missed = False
        if planned and not actual:
            try:
                if int(re.search(r"\d+", planned.get("target_tss", "0")).group()) > 30:
                    missed = True
            except Exception:
                pass
        by_day_out.append(
            {
                "date": d.isoformat(),
                "weekday": weekday,
                "planned": planned,
                "actual": [
                    {
                        "id": a["id"],
                        "sport": a["sport"],
                        "duration_min": round(a["duration_s"] / 60, 1),
                        "distance_km": round(a["distance_m"] / 1000.0, 2) if a.get("distance_m") else None,
                        "tss": round(a["tss"], 1) if a.get("tss") else None,
                        "tss_kind": a.get("tss_kind"),
                        "classified": _classify_session(a, ftp),
                    }
                    for a in actual
                ],
                "moved": moved,
                "missed": missed,
            }
        )

    planned_total_tss = 0.0
    for p in plan.values():
        try:
            planned_total_tss += float(re.search(r"[\d.]+", p.get("target_tss", "0")).group())
        except Exception:
            pass

    ramp = None
    if form_start and form_end:
        ramp = float(form_end["ctl"]) - float(form_start["ctl"])

    out = {
        "week": f"{iso_year}-{iso_week:02d}",
        "week_start": monday.isoformat(),
        "week_end": sunday.isoformat(),
        "plan_path": str(plan_path) if plan_path.exists() else None,
        "log_path": str(log_path) if log_path.exists() else None,
        "tss": {"planned": round(planned_total_tss, 1), "actual": round(actual_total_tss, 1)},
        "form": {
            "start": (
                {"date": form_start["date"], "ctl": round(float(form_start["ctl"]), 2),
                 "atl": round(float(form_start["atl"]), 2), "tsb": round(float(form_start["tsb"]), 2)}
                if form_start else None
            ),
            "end": (
                {"date": form_end["date"], "ctl": round(float(form_end["ctl"]), 2),
                 "atl": round(float(form_end["atl"]), 2), "tsb": round(float(form_end["tsb"]), 2)}
                if form_end else None
            ),
            "ctl_delta": round(ramp, 2) if ramp is not None else None,
        },
        "by_day": by_day_out,
        "session_distribution": distribution,
    }
    emit(out)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        fail(str(e))

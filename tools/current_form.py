"""current_form — today's CTL/ATL/TSB and form_state.

Read-only against pmc_daily. Run `compute_pmc.py` first if you've just
synced new activities.

Args: none.

Output:
    {
      "as_of": "YYYY-MM-DD",
      "ctl": float,
      "atl": float,
      "tsb": float,
      "ramp_7d": float | null,
      "form_state": "race-ready" | "neutral" | "productive" | "overreached" | "risky" | "crashing" | "detrained",
      "ramp_warning": bool,         # ramp_7d > +8 (warning territory per docs/training-science.md)
      "ramp_critical": bool,        # ramp_7d > +10 sustained 7d (crash territory)
      "citation": "docs/training-science.md#tsb-interpretation-thresholds",
      "history_14d": [{date, tss, ctl, atl, tsb}, ...]
    }
"""
from __future__ import annotations

import datetime as dt
import sys

from _common import emit, fail, open_db  # type: ignore[import-not-found]
from analysis.pmc import form_state

RAMP_WARN_THRESHOLD = 8.0
RAMP_CRASH_THRESHOLD = 10.0


def main(argv: list[str]) -> None:
    today = dt.date.today()
    seven_days_ago = today - dt.timedelta(days=7)
    fourteen_days_ago = today - dt.timedelta(days=14)

    with open_db() as conn:
        latest = conn.execute(
            "SELECT date, tss, ctl, atl, tsb FROM pmc_daily "
            "ORDER BY date DESC LIMIT 1"
        ).fetchone()
        if latest is None:
            fail(
                "pmc_daily is empty — run "
                "`uv run python tools/compute_pmc.py --backfill`"
            )

        earlier = conn.execute(
            "SELECT ctl FROM pmc_daily WHERE date <= ? ORDER BY date DESC LIMIT 1",
            (seven_days_ago.isoformat(),),
        ).fetchone()
        ramp = (
            float(latest["ctl"]) - float(earlier["ctl"]) if earlier else None
        )

        history = conn.execute(
            "SELECT date, tss, ctl, atl, tsb FROM pmc_daily "
            "WHERE date >= ? ORDER BY date",
            (fourteen_days_ago.isoformat(),),
        ).fetchall()

    state = form_state(float(latest["tsb"]), ramp)
    out = {
        "as_of": latest["date"],
        "ctl": round(float(latest["ctl"]), 2),
        "atl": round(float(latest["atl"]), 2),
        "tsb": round(float(latest["tsb"]), 2),
        "ramp_7d": round(ramp, 2) if ramp is not None else None,
        "form_state": state,
        "ramp_warning": ramp is not None and ramp > RAMP_WARN_THRESHOLD,
        "ramp_critical": ramp is not None and ramp > RAMP_CRASH_THRESHOLD,
        "citation": "docs/training-science.md#tsb-interpretation-thresholds",
        "history_14d": [
            {
                "date": r["date"],
                "tss": round(float(r["tss"]), 1),
                "ctl": round(float(r["ctl"]), 2),
                "atl": round(float(r["atl"]), 2),
                "tsb": round(float(r["tsb"]), 2),
            }
            for r in history
        ],
    }
    emit(out)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        fail(str(e))

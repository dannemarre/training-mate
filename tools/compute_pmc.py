"""compute_pmc — recompute pmc_daily from activities.

Args:
    --backfill           ignore the existing pmc_daily; rebuild from earliest activity (or 365 days ago, whichever is later)
    --recompute-days N   recompute last N days (default 14). Always at least 14 to cover edits.
    --through YYYY-MM-DD optional end date (default: today, local Stockholm)

Output:
    {
      "computed_through": "YYYY-MM-DD",
      "rows_written": N,
      "first_date": "YYYY-MM-DD",
      "ctl": ..., "atl": ..., "tsb": ..., "form_state": "...",
      "seed_ctl": ..., "seed_atl": ..., "seed_date": "YYYY-MM-DD"
    }

Strategy:
  1. Determine seed_date = day before recompute_start.
  2. Read existing pmc_daily for seed_date → seed_ctl / seed_atl. If absent
     and we're not backfilling, walk back to find the most recent day. If
     truly empty, backfill from earliest activity (or 365d ago).
  3. Aggregate activities by local date (Europe/Stockholm) into daily TSS.
  4. Fill missing days with TSS=0.
  5. Compute PMC and UPSERT into pmc_daily.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
import zoneinfo

from _common import emit, fail, log, open_db  # type: ignore[import-not-found]
from analysis.pmc import (
    compute_pmc,
    fill_missing_days,
    form_state,
)

LOCAL_TZ = zoneinfo.ZoneInfo("Europe/Stockholm")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--backfill", action="store_true")
    p.add_argument("--recompute-days", type=int, default=14)
    p.add_argument("--through")
    return p.parse_args(argv)


def _local_date(utc_iso: str) -> dt.date:
    """Parse a UTC ISO datetime string, return its date in Europe/Stockholm."""
    s = utc_iso.replace("Z", "+00:00")
    # Some rows might already have an offset; if not, treat as UTC.
    if "+" not in s and "-" not in s[10:]:
        s = s + "+00:00"
    return dt.datetime.fromisoformat(s).astimezone(LOCAL_TZ).date()


def main(argv: list[str]) -> None:
    args = _parse_args(argv)

    today = (
        dt.datetime.fromisoformat(args.through).date()
        if args.through
        else dt.datetime.now(LOCAL_TZ).date()
    )

    with open_db() as conn:
        # Earliest activity date in local TZ:
        earliest_row = conn.execute(
            "SELECT MIN(start_utc) AS first FROM activities"
        ).fetchone()
        if earliest_row is None or earliest_row["first"] is None:
            fail("no activities in DB — run sync_activities.py first")

        earliest_local = _local_date(earliest_row["first"])

        # Decide recompute window
        if args.backfill:
            start = max(earliest_local, today - dt.timedelta(days=365))
            seed_ctl = 0.0
            seed_atl = 0.0
            seed_date_str = (start - dt.timedelta(days=1)).isoformat()
            log(f"[pmc] BACKFILL from {start} (seed CTL=ATL=0)")
        else:
            recompute_start = today - dt.timedelta(days=max(args.recompute_days, 14))
            # Walk pmc_daily backwards from recompute_start to find a seed.
            seed_row = conn.execute(
                "SELECT date, ctl, atl FROM pmc_daily "
                "WHERE date <= ? ORDER BY date DESC LIMIT 1",
                (recompute_start.isoformat(),),
            ).fetchone()
            if seed_row is None:
                # No prior data; equivalent to a backfill
                start = max(earliest_local, today - dt.timedelta(days=365))
                seed_ctl = 0.0
                seed_atl = 0.0
                seed_date_str = (start - dt.timedelta(days=1)).isoformat()
                log(f"[pmc] no prior data — full backfill from {start}")
            else:
                seed_date = dt.date.fromisoformat(seed_row["date"])
                start = seed_date + dt.timedelta(days=1)
                seed_ctl = float(seed_row["ctl"])
                seed_atl = float(seed_row["atl"])
                seed_date_str = seed_row["date"]
                log(
                    f"[pmc] seeding from {seed_date_str} "
                    f"(CTL={seed_ctl:.1f}, ATL={seed_atl:.1f}); "
                    f"recompute {start}..{today}"
                )

        # Pull activities in window with local-date attribution
        rows = conn.execute(
            "SELECT start_utc, tss FROM activities "
            "WHERE start_utc >= ? AND tss IS NOT NULL "
            "ORDER BY start_utc",
            (
                dt.datetime.combine(start, dt.time.min, tzinfo=LOCAL_TZ)
                .astimezone(dt.timezone.utc)
                .isoformat(),
            ),
        ).fetchall()

        sparse: list[tuple[dt.date, float]] = []
        for r in rows:
            d = _local_date(r["start_utc"])
            if d <= today:
                sparse.append((d, float(r["tss"])))

        daily = fill_missing_days(sparse, start, today)
        pmc = compute_pmc(daily, seed_ctl=seed_ctl, seed_atl=seed_atl)

        # UPSERT
        n = 0
        for row in pmc:
            conn.execute(
                """
                INSERT INTO pmc_daily (date, tss, ctl, atl, tsb)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                  tss = excluded.tss,
                  ctl = excluded.ctl,
                  atl = excluded.atl,
                  tsb = excluded.tsb
                """,
                (row.date.isoformat(), row.tss, row.ctl, row.atl, row.tsb),
            )
            n += 1

        last = pmc[-1] if pmc else None

    out = {
        "computed_through": today.isoformat(),
        "rows_written": n,
        "first_date": pmc[0].date.isoformat() if pmc else None,
        "seed_ctl": seed_ctl,
        "seed_atl": seed_atl,
        "seed_date": seed_date_str,
    }
    if last is not None:
        out.update(
            {
                "ctl": round(last.ctl, 2),
                "atl": round(last.atl, 2),
                "tsb": round(last.tsb, 2),
                "form_state": form_state(last.tsb, None),
            }
        )

    emit(out)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception as e:  # noqa: BLE001
        fail(str(e))

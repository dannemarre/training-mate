"""estimate_ftp — propose an FTP from recent hard efforts.

Args:
    --method {recent_np,best_20min}  default: recent_np
    --window-days N                  default: 90
    --commit                         persist to ftp_history (otherwise dry-run)
    --note "..."                     attached to ftp_history.note when committed

Output:
    {
      "method": "...",
      "current_ftp": int|null,
      "proposed_ftp": int,
      "evidence": [{activity_id, np, duration_min, ...}, ...],
      "committed": bool,
      "effective_date": "YYYY-MM-DD" (when committed)
    }

Methods:
- `recent_np`: pick the highest 20+ min effort by NP in the last `window-days`.
  Propose `0.95 × that NP` (the standard 20-min test multiplier).
- `best_20min`: only considers activities where the duration is ≥20 min and the
  NP is at least 105% of current FTP — i.e. clearly above the current setting.

Run without `--commit` to inspect the proposal. With `--commit`, writes a row
to `ftp_history` with `effective_date = today`. PMC computations from then
on use the new value for activities ≥ that date.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys

from _common import (  # type: ignore[import-not-found]
    athlete_profile,
    emit,
    fail,
    open_db,
)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--method", choices=["recent_np", "best_20min"], default="recent_np")
    p.add_argument("--window-days", type=int, default=90)
    p.add_argument("--commit", action="store_true")
    p.add_argument("--note", default="")
    return p.parse_args(argv)


def main(argv: list[str]) -> None:
    args = _parse_args(argv)
    profile = athlete_profile()
    current_ftp = profile.get("ftp_w")
    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=args.window_days)).isoformat()

    with open_db() as conn:
        rows = conn.execute(
            """
            SELECT id, start_utc, sport, duration_s, np, intensity_factor, tss
            FROM activities
            WHERE start_utc >= ? AND np IS NOT NULL AND duration_s >= 1200
            ORDER BY np DESC
            LIMIT 5
            """,
            (cutoff,),
        ).fetchall()

    if not rows:
        emit(
            {
                "method": args.method,
                "current_ftp": current_ftp,
                "proposed_ftp": current_ftp,
                "evidence": [],
                "committed": False,
                "note": "no qualifying activities (≥20 min with NP) in window",
            }
        )
        return

    evidence = [
        {
            "activity_id": r["id"],
            "start_utc": r["start_utc"],
            "duration_min": round(r["duration_s"] / 60, 1),
            "np": round(r["np"], 1),
            "intensity_factor": round(r["intensity_factor"], 3) if r["intensity_factor"] else None,
            "tss": round(r["tss"], 1) if r["tss"] else None,
        }
        for r in rows
    ]

    top = rows[0]
    if args.method == "best_20min":
        if current_ftp and top["np"] < current_ftp * 1.05:
            proposed = int(current_ftp)
            note_pred = "no effort exceeds 105% of current FTP"
        else:
            proposed = int(round(top["np"] * 0.95))
            note_pred = "20-min test multiplier (0.95 × peak NP)"
    else:  # recent_np
        proposed = int(round(top["np"] * 0.95))
        note_pred = "0.95 × highest qualifying NP in window"

    committed = False
    effective_date = None
    if args.commit:
        effective_date = dt.date.today().isoformat()
        with open_db() as conn:
            conn.execute(
                "INSERT INTO ftp_history (effective_date, ftp_w, source, note) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(effective_date) DO UPDATE SET "
                "ftp_w = excluded.ftp_w, source = excluded.source, note = excluded.note",
                (
                    effective_date,
                    proposed,
                    f"estimate_ftp/{args.method}",
                    args.note or note_pred,
                ),
            )
            conn.execute(
                "UPDATE athlete_profile SET ftp_w = ?, updated_at = datetime('now') WHERE id = 1",
                (proposed,),
            )
            # Ensure the row exists (athlete_profile is single-row, may not be seeded)
            existing = conn.execute(
                "SELECT id FROM athlete_profile WHERE id = 1"
            ).fetchone()
            if existing is None:
                conn.execute(
                    "INSERT INTO athlete_profile (id, ftp_w, updated_at) VALUES (1, ?, datetime('now'))",
                    (proposed,),
                )
        committed = True

    emit(
        {
            "method": args.method,
            "current_ftp": current_ftp,
            "proposed_ftp": proposed,
            "evidence": evidence,
            "rationale": note_pred,
            "committed": committed,
            "effective_date": effective_date,
            "window_days": args.window_days,
        }
    )


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception as e:  # noqa: BLE001
        fail(str(e))

"""backfill — deep historical pull of Strava activities + Garmin wellness.

Args:
    --since YYYY-MM-DD       earliest date to pull (default: 2 years ago)
    --skip-strava            don't pull activities
    --skip-wellness          don't pull Garmin wellness
    --skip-segments          don't sync starred segments
    --chunk-days N           Garmin wellness chunk size (default 30) — useful for stop/resume
    --recompute-pmc          run compute_pmc --backfill after activities land
    --max-strava-pages N     cap Strava API pages (each page = ~30 activities)

Output:
    {
      "since": "...",
      "strava": {synced: N, skipped: M, errors: [...]},
      "wellness": {synced: N, errors: [...]},
      "segments": {synced: N, updated: M},
      "pmc": {rows_written: N, current_ctl: ..., current_atl: ..., current_tsb: ...}|null,
      "elapsed_s": float
    }

Strategy:
- Strava: paginated; stravalib auto-throttles to stay inside rate limits.
- Garmin wellness: chunked into `chunk_days` windows; sleeps 0.7 s per request.
  If a chunk 429s, the function logs and continues — you can re-run with the
  same --since to pick up where it left off (sync uses INSERT ... ON CONFLICT
  so it's idempotent).
- Segments: pulled once; cheap.
- PMC: optional --recompute-pmc rebuilds the full curve after activities land.

Re-running this tool is safe and idempotent. Useful pattern:
  uv run python tools/backfill.py --since 2024-01-01 --recompute-pmc
"""
from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
import time

from _common import REPO_ROOT, emit, fail, log, open_db  # type: ignore[import-not-found]


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--since", help="YYYY-MM-DD; default: 2 years ago")
    p.add_argument("--skip-strava", action="store_true")
    p.add_argument("--skip-wellness", action="store_true")
    p.add_argument("--skip-segments", action="store_true")
    p.add_argument("--chunk-days", type=int, default=30)
    p.add_argument("--recompute-pmc", action="store_true")
    p.add_argument("--max-strava-pages", type=int, default=None)
    return p.parse_args(argv)


def _backfill_strava(since: dt.datetime) -> dict:
    """Reuse sync_activities.py via subprocess — keeps the orchestration simple
    and inherits its existing throttling and error handling."""
    cmd = [
        "uv", "run", "python", "tools/sync_activities.py",
        "--since", since.date().isoformat(),
        "--no-garmin",
    ]
    log(f"[backfill] strava: {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=1800)
    if proc.stderr:
        # Show streamed status to the user
        for line in proc.stderr.splitlines()[-10:]:
            log(f"  {line}")
    if proc.returncode != 0:
        return {"error": f"sync_activities exit {proc.returncode}", "stderr_tail": proc.stderr[-500:]}
    import json as _json
    try:
        result = _json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        return {"error": "could not parse sync_activities output", "stdout_tail": proc.stdout[-500:]}
    return {
        "synced": result.get("synced", {}).get("strava", 0),
        "skipped": result.get("skipped", {}).get("strava", 0),
        "errors": result.get("errors", []),
    }


def _backfill_wellness(since: dt.date, chunk_days: int) -> dict:
    """Garmin wellness: chunk by `chunk_days` windows. Uses subprocess to
    sync_activities.py with --include-wellness --no-strava per chunk so
    each chunk is observable + recoverable."""
    today = dt.date.today()
    chunk_start = since
    total_synced = 0
    errors: list = []
    chunk_n = 0

    while chunk_start <= today:
        chunk_end = min(chunk_start + dt.timedelta(days=chunk_days - 1), today)
        chunk_n += 1
        log(f"[backfill] wellness chunk #{chunk_n}: {chunk_start} → {chunk_end}")
        cmd = [
            "uv", "run", "python", "tools/sync_activities.py",
            "--since", chunk_start.isoformat(),
            "--include-wellness",
            "--no-strava",
        ]
        proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=1800)
        if proc.returncode != 0:
            errors.append({"chunk": chunk_n, "stderr_tail": proc.stderr[-400:]})
            log(f"  chunk failed: {proc.stderr[-200:]}")
        else:
            import json as _json
            try:
                result = _json.loads(proc.stdout.strip().splitlines()[-1])
                synced = result.get("synced", {}).get("garmin_wellness", 0)
                total_synced += synced
                if result.get("errors"):
                    errors.extend(result["errors"])
                log(f"  +{synced} days; cumulative {total_synced}")
            except Exception:
                errors.append({"chunk": chunk_n, "parse_error": True, "stdout_tail": proc.stdout[-400:]})
        # Each chunk re-syncs from chunk_start to today so subsequent runs
        # re-cover ground; advance chunk_start by chunk_days to avoid that.
        chunk_start = chunk_end + dt.timedelta(days=1)
        # Garmin politeness break between chunks
        time.sleep(2.0)

    return {"synced": total_synced, "errors": errors, "chunks": chunk_n}


def _backfill_segments() -> dict:
    cmd = ["uv", "run", "python", "tools/sync_segments.py"]
    log(f"[backfill] segments: {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        return {"error": "sync_segments failed", "stderr_tail": proc.stderr[-400:]}
    import json as _json
    try:
        result = _json.loads(proc.stdout.strip().splitlines()[-1])
        return {"synced": result.get("synced", 0), "updated": result.get("updated", 0),
                "errors": result.get("errors", [])}
    except Exception:
        return {"error": "parse failed", "stdout_tail": proc.stdout[-400:]}


def _recompute_pmc() -> dict:
    cmd = ["uv", "run", "python", "tools/compute_pmc.py", "--backfill"]
    log(f"[backfill] pmc: {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        return {"error": "compute_pmc failed", "stderr_tail": proc.stderr[-400:]}
    import json as _json
    try:
        return _json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        return {"error": "parse failed", "stdout_tail": proc.stdout[-400:]}


def main(argv: list[str]) -> None:
    args = _parse_args(argv)
    started = time.time()

    if args.since:
        since_dt = dt.datetime.fromisoformat(args.since).replace(tzinfo=dt.timezone.utc)
    else:
        since_dt = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=730)

    out: dict = {
        "since": since_dt.date().isoformat(),
        "strava": None,
        "wellness": None,
        "segments": None,
        "pmc": None,
    }

    if not args.skip_strava:
        out["strava"] = _backfill_strava(since_dt)

    if not args.skip_wellness:
        out["wellness"] = _backfill_wellness(since_dt.date(), args.chunk_days)

    if not args.skip_segments:
        out["segments"] = _backfill_segments()

    if args.recompute_pmc:
        out["pmc"] = _recompute_pmc()

    out["elapsed_s"] = round(time.time() - started, 1)

    # Quick post-state summary so the agent can see the result without
    # running data_status separately.
    with open_db() as conn:
        n = conn.execute("SELECT COUNT(*) AS n FROM activities").fetchone()["n"]
        wn = conn.execute("SELECT COUNT(*) AS n FROM wellness_daily").fetchone()["n"]
        out["post_state"] = {
            "activity_rows": n,
            "wellness_rows": wn,
        }

    emit(out)


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception as e:  # noqa: BLE001
        fail(str(e))

"""rate_limits — 24-hour API usage from `rate_limit_log`.

Args:
    --window-h N   default 24

Output:
    {"by_provider": {"strava": {requests: N, last_seen_quota: {...}}, ...},
     "warnings": [...]}
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys

from _common import emit, open_db  # type: ignore[import-not-found]


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--window-h", type=int, default=24)
    return p.parse_args(argv)


def main(argv: list[str]) -> None:
    args = _parse_args(argv)
    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=args.window_h)).isoformat()

    with open_db() as conn:
        rows = conn.execute(
            "SELECT provider, ts_utc, window_used, window_limit, day_used, day_limit, endpoint "
            "FROM rate_limit_log WHERE ts_utc >= ? "
            "ORDER BY provider, ts_utc DESC",
            (cutoff,),
        ).fetchall()

    by_provider: dict = {}
    for r in rows:
        prov = r["provider"]
        if prov not in by_provider:
            by_provider[prov] = {
                "requests": 0,
                "last_window_used": r["window_used"],
                "last_window_limit": r["window_limit"],
                "last_day_used": r["day_used"],
                "last_day_limit": r["day_limit"],
                "last_seen_at": r["ts_utc"],
            }
        by_provider[prov]["requests"] += 1

    warnings = []
    for prov, info in by_provider.items():
        if info["last_window_limit"] and info["last_window_used"]:
            pct = info["last_window_used"] / info["last_window_limit"]
            if pct > 0.8:
                warnings.append(
                    f"{prov}: window usage {info['last_window_used']}/{info['last_window_limit']} "
                    f"({pct*100:.0f}%) — back off"
                )
        if info["last_day_limit"] and info["last_day_used"]:
            pct = info["last_day_used"] / info["last_day_limit"]
            if pct > 0.8:
                warnings.append(
                    f"{prov}: daily usage {info['last_day_used']}/{info['last_day_limit']} "
                    f"({pct*100:.0f}%) — defer non-essential pulls until midnight"
                )

    emit({"window_h": args.window_h, "by_provider": by_provider, "warnings": warnings})


if __name__ == "__main__":
    main(sys.argv[1:])

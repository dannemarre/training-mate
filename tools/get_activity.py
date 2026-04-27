"""get_activity — full detail for one activity, optionally with stream summaries.

Args:
    --id N                    DB primary key of the activity row (required)
    --include-streams         attach decoded stream summaries (length, mean, etc.)
    --include-stream-data     attach the full decoded numpy arrays as lists (heavy)

Output:
    {
      activity: {... full row ...},
      streams: {
         "power": {"length": N, "mean": ..., "max": ..., "data": [...] (if --include-stream-data)},
         "hr":    {...},
         ...
      }
    }
"""
from __future__ import annotations

import argparse
import sys
from typing import Any

import numpy as np
from _common import decode_stream, emit, fail, open_db  # type: ignore[import-not-found]


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--id", type=int, required=True)
    p.add_argument("--include-streams", action="store_true")
    p.add_argument("--include-stream-data", action="store_true")
    return p.parse_args(argv)


def _stream_summary(arr: np.ndarray) -> dict[str, Any]:
    return {
        "length": int(len(arr)),
        "mean": float(np.mean(arr)) if len(arr) else None,
        "max": float(np.max(arr)) if len(arr) else None,
        "min": float(np.min(arr)) if len(arr) else None,
    }


def main(argv: list[str]) -> None:
    args = _parse_args(argv)
    with open_db() as conn:
        row = conn.execute(
            "SELECT * FROM activities WHERE id = ?", (args.id,)
        ).fetchone()
        if row is None:
            fail(f"activity id={args.id} not found")
        activity = dict(row)
        # Don't dump the full Strava `raw` blob into stdout by default — it's huge
        if "raw" in activity and isinstance(activity["raw"], (str, bytes)):
            activity["raw_present"] = True
            del activity["raw"]

        streams_out: dict[str, dict[str, Any]] = {}
        if args.include_streams or args.include_stream_data:
            stream_rows = conn.execute(
                "SELECT kind, sample_hz, blob FROM activity_streams WHERE activity_id = ?",
                (args.id,),
            ).fetchall()
            for sr in stream_rows:
                arr = decode_stream(sr["blob"])
                summary = _stream_summary(arr)
                summary["sample_hz"] = sr["sample_hz"]
                if args.include_stream_data:
                    summary["data"] = arr.tolist()
                streams_out[sr["kind"]] = summary

    emit({"activity": activity, "streams": streams_out})


if __name__ == "__main__":
    main(sys.argv[1:])

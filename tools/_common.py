"""Shared helpers for training-mate CLI tools.

Tool contract:
- Run as `uv run python tools/<name>.py [args]`.
- stdout: one JSON object.
- stderr: human-readable logs.
- Exit 0 on success; non-zero with `{"error": "..."}` on stdout for failures.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
DB_PATH = DATA_DIR / "training-mate.sqlite"

# Make sibling packages (e.g. `analysis`) importable from any tool that
# imports _common. Tools are run as `uv run python tools/<name>.py`, which
# puts `tools/` on sys.path but not the repo root. Adding REPO_ROOT here
# means `from analysis.tss import ...` Just Works in every tool.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

STRAVA_TOKEN_PATH = Path.home() / ".config" / "strava-mcp" / "config.json"
GARMIN_TOKEN_DIR = Path.home() / ".garmin-mcp"
GOOGLE_CALENDAR_TOKEN_DIR_DEFAULT = Path.home() / ".config" / "google-calendar-mcp"

SCHEMA_VERSION = 1


def google_calendar_token_dir() -> Path:
    """Where @cocal/google-calendar-mcp stores OAuth tokens.

    Defaults to ~/.config/google-calendar-mcp/, overridable via
    GOOGLE_CALENDAR_MCP_TOKEN_PATH.
    """
    _load_env()
    override = os.getenv("GOOGLE_CALENDAR_MCP_TOKEN_PATH")
    return Path(override).expanduser() if override else GOOGLE_CALENDAR_TOKEN_DIR_DEFAULT


def calendar_name() -> str:
    _load_env()
    return os.getenv("TM_CALENDAR_NAME", "Training")


def _load_env() -> None:
    load_dotenv(REPO_ROOT / ".env", override=False)


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def emit(payload: dict[str, Any]) -> None:
    json.dump(payload, sys.stdout, default=str, ensure_ascii=False)
    sys.stdout.write("\n")
    sys.stdout.flush()


def fail(message: str, code: int = 1, **extra: Any) -> None:
    payload: dict[str, Any] = {"error": message}
    payload.update(extra)
    emit(payload)
    sys.exit(code)


# ---------------------------------------------------------------------------
# Stream compression — used by activity_streams.blob
# ---------------------------------------------------------------------------


def encode_stream(arr: Any) -> bytes:
    """Compress a 1-D numpy array to bytes for `activity_streams.blob`.

    Uses numpy.savez_compressed (gzip-based). No external compression
    dependency required. Schema docs say "zstd-compressed" — that's
    aspirational; the blob format is opaque to readers and can be migrated
    later if size becomes an issue.
    """
    import io

    import numpy as np

    buf = io.BytesIO()
    np.savez_compressed(buf, data=np.asarray(arr))
    return buf.getvalue()


def decode_stream(blob: bytes) -> Any:
    """Inverse of `encode_stream`. Returns a numpy ndarray."""
    import io

    import numpy as np

    buf = io.BytesIO(blob)
    return np.load(buf)["data"]


# ---------------------------------------------------------------------------
# Athlete profile helpers — used by everything that needs FTP / LTHR / RHR.
# ---------------------------------------------------------------------------


def athlete_profile() -> dict[str, Any]:
    """Read row id=1 from athlete_profile, with sensible defaults if NULL.

    Returns a dict with FTP / LTHR / max_hr / RHR / weight / etc. Defaults
    are placeholder; tools should surface "using placeholder, please confirm"
    when the underlying field is None.
    """
    DEFAULTS = {
        "ftp_w": 240,
        "lthr": 165,
        "max_hr": 190,
        "rhr": 50,
        "weight_kg": 75.0,
        "run_threshold_pace_s_per_km": 270.0,  # 4:30/km
        "timezone": "Europe/Stockholm",
    }
    with open_db() as conn:
        row = conn.execute(
            "SELECT ftp_w, lthr, max_hr, rhr, weight_kg, "
            "run_threshold_pace_s_per_km, timezone "
            "FROM athlete_profile WHERE id = 1"
        ).fetchone()
    if row is None:
        return {**DEFAULTS, "from_db": False}
    out = dict(row)
    placeholders_used: list[str] = []
    for k, v in DEFAULTS.items():
        if out.get(k) is None:
            out[k] = v
            placeholders_used.append(k)
    out["from_db"] = True
    out["placeholders_used"] = placeholders_used
    return out


def ftp_at(date_iso: str) -> int:
    """Return FTP active on a given local date (YYYY-MM-DD).

    Walks `ftp_history` for the most recent `effective_date` ≤ `date_iso`.
    Falls back to `athlete_profile.ftp_w`, then to the placeholder default.
    """
    with open_db() as conn:
        row = conn.execute(
            "SELECT ftp_w FROM ftp_history "
            "WHERE effective_date <= ? "
            "ORDER BY effective_date DESC LIMIT 1",
            (date_iso,),
        ).fetchone()
        if row is not None:
            return int(row["ftp_w"])
    return int(athlete_profile()["ftp_w"])


# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------

MIGRATIONS: list[str] = [
    # v1: schema bootstrap
    """
    CREATE TABLE IF NOT EXISTS athlete_profile (
      id              INTEGER PRIMARY KEY CHECK (id = 1),
      name            TEXT,
      weight_kg       REAL,
      ftp_w           INTEGER,
      lthr            INTEGER,
      max_hr          INTEGER,
      rhr             INTEGER,
      run_threshold_pace_s_per_km REAL,
      sex             TEXT,
      timezone        TEXT,
      updated_at      TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS ftp_history (
      effective_date  TEXT NOT NULL PRIMARY KEY,
      ftp_w           INTEGER NOT NULL,
      source          TEXT,
      note            TEXT
    );

    CREATE TABLE IF NOT EXISTS activities (
      id              INTEGER PRIMARY KEY AUTOINCREMENT,
      source          TEXT NOT NULL,           -- 'strava' | 'garmin'
      source_id       TEXT NOT NULL,
      sport           TEXT NOT NULL,
      start_utc       TEXT NOT NULL,
      duration_s      INTEGER NOT NULL,
      distance_m      REAL,
      avg_power       REAL,
      np              REAL,
      intensity_factor REAL,
      tss             REAL,
      tss_kind        TEXT,                    -- 'power' | 'hr' | 'pace'
      kj              REAL,
      avg_hr          REAL,
      max_hr          REAL,
      elevation_gain_m REAL,
      polyline        TEXT,
      raw             TEXT,                    -- json blob from source
      np_low_confidence INTEGER NOT NULL DEFAULT 0,
      created_at      TEXT NOT NULL,
      UNIQUE (source, source_id)
    );
    CREATE INDEX IF NOT EXISTS idx_activities_start_utc ON activities (start_utc);

    CREATE TABLE IF NOT EXISTS activity_streams (
      activity_id     INTEGER NOT NULL,
      kind            TEXT NOT NULL,           -- power | hr | cadence | speed | altitude | latlng | time | grade
      sample_hz       REAL,
      blob            BLOB NOT NULL,           -- zstd-compressed numpy bytes
      PRIMARY KEY (activity_id, kind),
      FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS wellness_daily (
      date            TEXT PRIMARY KEY,        -- local YYYY-MM-DD
      hrv_ms          REAL,
      body_battery    INTEGER,
      readiness       INTEGER,
      sleep_score     INTEGER,
      sleep_minutes   INTEGER,
      resting_hr      INTEGER,
      raw             TEXT
    );

    CREATE TABLE IF NOT EXISTS pmc_daily (
      date            TEXT PRIMARY KEY,        -- local YYYY-MM-DD
      tss             REAL NOT NULL DEFAULT 0,
      ctl             REAL NOT NULL,
      atl             REAL NOT NULL,
      tsb             REAL NOT NULL
    );

    CREATE TABLE IF NOT EXISTS segments (
      id              INTEGER PRIMARY KEY,     -- strava segment id
      name            TEXT NOT NULL,
      distance_m      REAL,
      avg_grade       REAL,
      bearing_deg     REAL,                    -- precomputed start->end bearing
      polyline        TEXT,
      kom_time_s      INTEGER,
      kom_avg_w       REAL,
      starred         INTEGER NOT NULL DEFAULT 0,
      raw             TEXT
    );

    CREATE TABLE IF NOT EXISTS segment_efforts (
      id              INTEGER PRIMARY KEY,     -- strava effort id
      segment_id      INTEGER NOT NULL,
      activity_id     INTEGER,
      start_utc       TEXT NOT NULL,
      elapsed_s       INTEGER NOT NULL,
      avg_power       REAL,
      avg_hr          REAL,
      pr_rank         INTEGER,
      FOREIGN KEY (segment_id) REFERENCES segments(id)
    );

    CREATE TABLE IF NOT EXISTS routes (
      id              INTEGER PRIMARY KEY,
      name            TEXT NOT NULL,
      distance_m      REAL,
      elevation_gain_m REAL,
      polyline        TEXT,
      raw             TEXT
    );

    CREATE TABLE IF NOT EXISTS plans (
      id              INTEGER PRIMARY KEY AUTOINCREMENT,
      week_start      TEXT NOT NULL,           -- Monday, local YYYY-MM-DD
      created_at      TEXT NOT NULL,
      notes           TEXT
    );

    CREATE TABLE IF NOT EXISTS workouts (
      id              INTEGER PRIMARY KEY AUTOINCREMENT,
      plan_id         INTEGER,
      scheduled_date  TEXT NOT NULL,           -- local YYYY-MM-DD
      sport           TEXT NOT NULL,
      kind            TEXT NOT NULL,           -- sst | vo2 | threshold | endurance | recovery | race
      duration_min    INTEGER NOT NULL,
      target_tss      REAL,
      structure_json  TEXT NOT NULL,           -- intervals
      executed_activity_id INTEGER,
      FOREIGN KEY (plan_id) REFERENCES plans(id),
      FOREIGN KEY (executed_activity_id) REFERENCES activities(id)
    );

    CREATE TABLE IF NOT EXISTS weather_forecast (
      id              INTEGER PRIMARY KEY AUTOINCREMENT,
      lat             REAL NOT NULL,
      lon             REAL NOT NULL,
      hour_utc        TEXT NOT NULL,
      temp_c          REAL,
      wind_kmh        REAL,
      wind_dir_from_deg REAL,
      precip_mm       REAL,
      fetched_at      TEXT NOT NULL,
      UNIQUE (lat, lon, hour_utc)
    );

    CREATE TABLE IF NOT EXISTS rate_limit_log (
      id              INTEGER PRIMARY KEY AUTOINCREMENT,
      provider        TEXT NOT NULL,           -- 'strava' | 'garmin'
      ts_utc          TEXT NOT NULL,
      window_used     INTEGER,
      window_limit    INTEGER,
      day_used        INTEGER,
      day_limit       INTEGER,
      endpoint        TEXT
    );
    """,
]


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _migrate(conn: sqlite3.Connection) -> None:
    cur = conn.execute("PRAGMA user_version")
    current = int(cur.fetchone()[0])
    if current >= SCHEMA_VERSION:
        return
    log(f"[db] migrating from v{current} to v{SCHEMA_VERSION}")
    for i in range(current, SCHEMA_VERSION):
        conn.executescript(MIGRATIONS[i])
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()


@contextmanager
def open_db():  # type: ignore[no-untyped-def]
    _ensure_data_dir()
    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        _migrate(conn)
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Auth — read upstream MCP servers' on-disk token caches.
# ---------------------------------------------------------------------------


@dataclass
class StravaTokens:
    client_id: str | None
    client_secret: str | None
    access_token: str | None
    refresh_token: str | None
    expires_at: int | None


def load_strava_tokens() -> StravaTokens:
    """Read tokens written by @r-huijts/strava-mcp-server.

    Per its README, env > config file > .env. We mirror that:
    env wins (so users can override during dev), then the config.json.
    """
    _load_env()
    cfg: dict[str, Any] = {}
    if STRAVA_TOKEN_PATH.exists():
        try:
            cfg = json.loads(STRAVA_TOKEN_PATH.read_text())
        except json.JSONDecodeError as e:
            log(f"[strava] token file unreadable: {e}")

    def pick(env_key: str, cfg_key: str) -> str | None:
        return os.getenv(env_key) or cfg.get(cfg_key)

    # Upstream @r-huijts/strava-mcp-server writes camelCase keys (clientId, accessToken, …)
    # to ~/.config/strava-mcp/config.json. Env vars stay UPPER_SNAKE.
    return StravaTokens(
        client_id=pick("STRAVA_CLIENT_ID", "clientId"),
        client_secret=pick("STRAVA_CLIENT_SECRET", "clientSecret"),
        access_token=pick("STRAVA_ACCESS_TOKEN", "accessToken"),
        refresh_token=pick("STRAVA_REFRESH_TOKEN", "refreshToken"),
        expires_at=cfg.get("expiresAt"),
    )


def strava_client():  # type: ignore[no-untyped-def]
    """Return a stravalib Client with tokens applied. Lazy import."""
    from stravalib import Client  # type: ignore[import-not-found]

    tokens = load_strava_tokens()
    if not tokens.access_token:
        raise RuntimeError(
            "Strava access token missing. Run the strava-mcp server once to authorize: "
            "`npx -y @r-huijts/strava-mcp-server` and complete the OAuth flow."
        )
    client = Client(access_token=tokens.access_token)
    return client, tokens


def garmin_token_paths() -> tuple[Path, Path, Path, Path]:
    """Return (legacy_oauth1, legacy_oauth2, legacy_profile, modern_tokens).

    python-garminconnect ≥ 0.3.3 writes a single `garmin_tokens.json`. The
    legacy garth-style pair is still recognised so old caches keep working
    until they expire.
    """
    return (
        GARMIN_TOKEN_DIR / "oauth1_token.json",
        GARMIN_TOKEN_DIR / "oauth2_token.json",
        GARMIN_TOKEN_DIR / "profile.json",
        GARMIN_TOKEN_DIR / "garmin_tokens.json",
    )


def garmin_tokens_present() -> bool:
    """True if either the modern or legacy Garmin token cache is on disk."""
    oauth1, oauth2, _profile, modern = garmin_token_paths()
    return modern.exists() or (oauth1.exists() and oauth2.exists())


def garmin_client():  # type: ignore[no-untyped-def]
    """Return a logged-in garminconnect.Garmin resumed from ~/.garmin-mcp/.

    Uses python-garminconnect ≥ 0.3.3's native SSO (matin/garth was deprecated
    2026-03-28). `Garmin().login(tokenstore=...)` loads from a directory that
    can hold either the modern `garmin_tokens.json` or the legacy garth pair.
    """
    from garminconnect import Garmin  # type: ignore[import-not-found]

    if not garmin_tokens_present():
        raise RuntimeError(
            "Garmin tokens missing under ~/.garmin-mcp/. Run setup once: "
            "`uv run python tools/garmin_auth_setup.py` (interactive — needs MFA)."
        )
    client = Garmin(retry_attempts=1)
    client.login(tokenstore=str(GARMIN_TOKEN_DIR))
    return client


def garmin_dryrun() -> bool:
    _load_env()
    return os.getenv("TM_GARMIN_DRYRUN", "true").lower() not in ("0", "false", "no")


__all__ = [
    "DATA_DIR",
    "DB_PATH",
    "GARMIN_TOKEN_DIR",
    "GOOGLE_CALENDAR_TOKEN_DIR_DEFAULT",
    "STRAVA_TOKEN_PATH",
    "StravaTokens",
    "calendar_name",
    "emit",
    "fail",
    "garmin_client",
    "garmin_dryrun",
    "garmin_token_paths",
    "google_calendar_token_dir",
    "load_strava_tokens",
    "log",
    "open_db",
    "strava_client",
]

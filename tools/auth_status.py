"""auth_status — report Strava + Garmin token health.

Outputs JSON:
{
  "strava": {"ok": bool, "client_id": bool, "access_token": bool, "expires_at": int|null,
             "expires_in_s": int|null, "config_path": str},
  "garmin": {"ok": bool, "oauth1_present": bool, "oauth2_present": bool,
             "profile": {"displayName": str, "profileId": int}|null,
             "token_dir": str},
  "db":     {"path": str, "exists": bool, "schema_version": int}
}
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from _common import (  # type: ignore[import-not-found]
    DB_PATH,
    GARMIN_TOKEN_DIR,
    STRAVA_TOKEN_PATH,
    emit,
    garmin_token_paths,
    load_strava_tokens,
    open_db,
)


def strava_status() -> dict:
    t = load_strava_tokens()
    expires_in: int | None = None
    if t.expires_at:
        expires_in = int(t.expires_at - time.time())
    return {
        "ok": bool(t.access_token),
        "client_id": bool(t.client_id),
        "access_token": bool(t.access_token),
        "refresh_token": bool(t.refresh_token),
        "expires_at": t.expires_at,
        "expires_in_s": expires_in,
        "config_path": str(STRAVA_TOKEN_PATH),
    }


def garmin_status() -> dict:
    oauth1, oauth2, profile = garmin_token_paths()
    profile_data: dict | None = None
    if profile.exists():
        try:
            profile_data = json.loads(profile.read_text())
        except json.JSONDecodeError:
            profile_data = None
    return {
        "ok": oauth1.exists() and oauth2.exists(),
        "oauth1_present": oauth1.exists(),
        "oauth2_present": oauth2.exists(),
        "profile": profile_data,
        "token_dir": str(GARMIN_TOKEN_DIR),
    }


def db_status() -> dict:
    exists_before = Path(DB_PATH).exists()
    with open_db() as conn:
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    return {
        "path": str(DB_PATH),
        "existed_before": exists_before,
        "schema_version": version,
    }


def main() -> None:
    emit({
        "strava": strava_status(),
        "garmin": garmin_status(),
        "db": db_status(),
    })


if __name__ == "__main__":
    main()

"""auth_status — report Strava + Garmin + Google Calendar token health.

Outputs JSON:
{
  "strava": {"ok": bool, "client_id": bool, "access_token": bool, "expires_at": int|null,
             "expires_in_s": int|null, "config_path": str},
  "garmin": {"ok": bool, "oauth1_present": bool, "oauth2_present": bool,
             "profile": {"displayName": str, "profileId": int}|null,
             "token_dir": str},
  "google_calendar": {"ok": bool, "credentials_path": str|null,
                      "credentials_present": bool, "token_dir": str,
                      "token_files": [str], "calendar_name": str},
  "db":     {"path": str, "exists": bool, "schema_version": int}
}
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from _common import (  # type: ignore[import-not-found]
    DB_PATH,
    GARMIN_TOKEN_DIR,
    STRAVA_TOKEN_PATH,
    calendar_name,
    emit,
    garmin_token_paths,
    google_calendar_token_dir,
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


def google_calendar_status() -> dict:
    creds_env = os.getenv("GOOGLE_OAUTH_CREDENTIALS")
    creds_path = Path(creds_env).expanduser() if creds_env else None
    creds_present = bool(creds_path and creds_path.exists())

    token_dir = google_calendar_token_dir()
    token_files: list[str] = []
    if token_dir.exists():
        token_files = sorted(p.name for p in token_dir.iterdir() if p.is_file())

    return {
        "ok": creds_present and bool(token_files),
        "credentials_path": str(creds_path) if creds_path else None,
        "credentials_present": creds_present,
        "token_dir": str(token_dir),
        "token_files": token_files,
        "calendar_name": calendar_name(),
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
        "google_calendar": google_calendar_status(),
        "db": db_status(),
    })


if __name__ == "__main__":
    main()

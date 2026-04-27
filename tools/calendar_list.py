"""calendar_list — read events from the Training Mate calendar.

Args:
    --from YYYY-MM-DD     start date (inclusive); default: today
    --to   YYYY-MM-DD     end date (exclusive);   default: from + 7 days
    --calendar STR        override TM_CALENDAR_NAME
    --json-only           don't print summary lines, just the JSON

Output:
    {"calendar_name": "...", "calendar_id": "...", "from": "...", "to": "...",
     "events": [{id, summary, start, end, description, htmlLink}, ...]}

Reads OAuth credentials from `~/.config/google-calendar-mcp/gcp-oauth.keys.json`
and tokens from `~/.config/google-calendar-mcp/tokens.json` (written by the
upstream MCP server's first-time auth dance — see PLAN.md "Pending user setup").
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from _common import (  # type: ignore[import-not-found]
    calendar_name as default_calendar_name,
    emit,
    fail,
    google_calendar_token_dir,
    log,
)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--from", dest="from_date", help="YYYY-MM-DD; default today")
    p.add_argument("--to", dest="to_date", help="YYYY-MM-DD; default from+7d")
    p.add_argument("--calendar", help="override TM_CALENDAR_NAME")
    p.add_argument("--json-only", action="store_true")
    return p.parse_args(argv)


def _build_service():
    """Build a googleapiclient `service` object using stored OAuth tokens."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    token_dir = google_calendar_token_dir()
    tokens_path = token_dir / "tokens.json"
    creds_path = token_dir / "gcp-oauth.keys.json"

    if not tokens_path.exists():
        fail(
            "Calendar tokens missing. Run `npx -y @cocal/google-calendar-mcp auth` first."
        )

    tokens_doc = json.loads(tokens_path.read_text())
    # The cocal MCP stores per-account: top-level keys like "normal", "work".
    # Default account is "normal"; if absent, use the first account in the doc.
    account_doc = tokens_doc.get("normal")
    if account_doc is None:
        if "accounts" in tokens_doc:
            account_doc = next(iter(tokens_doc["accounts"].values()))
        elif "tokens" in tokens_doc:
            account_doc = tokens_doc["tokens"]
        elif tokens_doc and isinstance(tokens_doc, dict):
            # Single-account shape with the account key at top level (e.g. "normal")
            account_doc = next(iter(tokens_doc.values())) if tokens_doc else {}
        else:
            account_doc = {}
    if not isinstance(account_doc, dict):
        account_doc = {}

    access = (
        account_doc.get("access_token")
        or account_doc.get("accessToken")
        or account_doc.get("token")
    )
    refresh = account_doc.get("refresh_token") or account_doc.get("refreshToken")
    expiry_iso = (
        account_doc.get("expiry")
        or account_doc.get("expiresAt")
        or account_doc.get("expiry_date")  # cocal MCP — ms since epoch
    )

    creds_doc = json.loads(creds_path.read_text()) if creds_path.exists() else {}
    installed = creds_doc.get("installed") or creds_doc.get("web") or {}
    client_id = installed.get("client_id")
    client_secret = installed.get("client_secret")
    token_uri = installed.get("token_uri", "https://oauth2.googleapis.com/token")

    expiry = None
    if isinstance(expiry_iso, (int, float)):
        # Some clients store expiry in milliseconds since epoch
        secs = expiry_iso / 1000 if expiry_iso > 1e12 else expiry_iso
        expiry = dt.datetime.fromtimestamp(secs, tz=dt.timezone.utc).replace(tzinfo=None)
    elif isinstance(expiry_iso, str):
        try:
            expiry = dt.datetime.fromisoformat(expiry_iso.replace("Z", "+00:00")).astimezone(dt.timezone.utc).replace(tzinfo=None)
        except ValueError:
            pass

    creds = Credentials(
        token=access,
        refresh_token=refresh,
        token_uri=token_uri,
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/calendar"],
        expiry=expiry,
    )
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())

    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _find_calendar_id(service, name: str) -> tuple[str, str]:
    page = None
    while True:
        cl = service.calendarList().list(pageToken=page).execute()
        for entry in cl.get("items", []):
            if entry.get("summary") == name or entry.get("summaryOverride") == name:
                return entry["id"], entry.get("summary") or entry.get("summaryOverride")
        page = cl.get("nextPageToken")
        if not page:
            break
    fail(f"calendar named {name!r} not found in this Google account.")


def main(argv: list[str]) -> None:
    args = _parse_args(argv)
    name = args.calendar or default_calendar_name()
    today = dt.date.today()
    from_d = dt.date.fromisoformat(args.from_date) if args.from_date else today
    to_d = dt.date.fromisoformat(args.to_date) if args.to_date else (from_d + dt.timedelta(days=7))

    service = _build_service()
    cal_id, cal_summary = _find_calendar_id(service, name)
    if not args.json_only:
        log(f"[calendar] {cal_summary} ({cal_id}) {from_d}..{to_d}")

    time_min = dt.datetime.combine(from_d, dt.time.min, tzinfo=dt.timezone.utc).isoformat()
    time_max = dt.datetime.combine(to_d, dt.time.min, tzinfo=dt.timezone.utc).isoformat()

    events: list[dict] = []
    page = None
    while True:
        resp = (
            service.events()
            .list(
                calendarId=cal_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
                pageToken=page,
            )
            .execute()
        )
        for e in resp.get("items", []):
            events.append(
                {
                    "id": e.get("id"),
                    "summary": e.get("summary"),
                    "start": e.get("start"),
                    "end": e.get("end"),
                    "description": e.get("description"),
                    "htmlLink": e.get("htmlLink"),
                }
            )
        page = resp.get("nextPageToken")
        if not page:
            break

    emit(
        {
            "calendar_name": cal_summary,
            "calendar_id": cal_id,
            "from": from_d.isoformat(),
            "to": to_d.isoformat(),
            "events": events,
        }
    )


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        fail(f"{type(e).__name__}: {e}")

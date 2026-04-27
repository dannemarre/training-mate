"""garmin_auth_setup — interactive first-time Garmin SSO + MFA dance.

Reads GARMIN_EMAIL / GARMIN_PASSWORD from .env, prompts for MFA on stderr,
saves tokens to ~/.garmin-mcp/garmin_tokens.json (modern python-garminconnect
≥ 0.3.3 format — `matin/garth` was deprecated 2026-03-28).

Re-run on token expiry (~1 year) or after a password change.

Output:
{
  "ok": bool,
  "token_dir": str,
  "user": str,        # the GARMIN_EMAIL we logged in with
  "profile_id": int,  # Garmin's internal profile id (for sanity check)
  "format": "modern"
}

stderr surfaces the SSO progress and the MFA prompt; this tool requires a
real terminal because of the `input()` for the MFA code. Run as:
  uv run python tools/garmin_auth_setup.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from _common import GARMIN_TOKEN_DIR, REPO_ROOT, emit, fail, log


def prompt_mfa() -> str:
    print("Garmin MFA code: ", end="", flush=True, file=sys.stderr)
    return input().strip()


def main() -> None:
    load_dotenv(REPO_ROOT / ".env", override=False)
    email = os.environ.get("GARMIN_EMAIL")
    password = os.environ.get("GARMIN_PASSWORD")
    if not email or not password:
        fail("GARMIN_EMAIL or GARMIN_PASSWORD missing from .env")

    log(f"[garmin] SSO for {email} → {GARMIN_TOKEN_DIR}")

    # Lazy import so the deprecation warning doesn't fire on auth_status etc.
    from garminconnect import Garmin  # type: ignore[import-not-found]

    GARMIN_TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    client = Garmin(
        email=email,
        password=password,
        prompt_mfa=prompt_mfa,
        retry_attempts=1,  # do NOT compound a 429
    )
    try:
        client.login(tokenstore=str(GARMIN_TOKEN_DIR))
    except Exception as e:
        fail(f"login failed: {type(e).__name__}: {e}")

    profile = client.connectapi("/userprofile-service/socialProfile") or {}
    emit({
        "ok": True,
        "token_dir": str(GARMIN_TOKEN_DIR),
        "user": email,
        "profile_id": profile.get("profileId"),
        "full_name": profile.get("fullName"),
        "format": "modern",
    })


if __name__ == "__main__":
    main()

# Training-Mate — plan of record

This file is the durable plan for the project. Edit as decisions land.
Companion files: `CLAUDE.md` (athlete + rules), `docs/*.md` (curated knowledge), `tools/*.py` (CLI tools), `.claude/{agents,commands}/` (subagents + skills), `journal/*.md` (training diary).

---

## Current status (2026-04-27)

**Done:**
- **M1 — project skeleton.** `pyproject.toml`, `.gitignore`, `.env.example`, `.mcp.json` (Strava + Garmin), `tools/_common.py` (db handle, token loaders, JSON helpers), `tools/auth_status.py`, SQLite schema v1 with migrations, `docs/tools.md` + `docs/schema.md` stubs, `CLAUDE.md` v0.
- **M1.5 — personal context + Calendar wiring + journal scaffolding.**
  - `CLAUDE.md` filled in with Martin's profile (Ängby CC, Stockholm, right-knee rehab, gym at work, Sunday Ängby söndag as the weekly anchor). Single-device assumption explicitly noted.
  - `docs/group-rides.md` — Stockholm regular rides (Ängby söndag, Onsdagsgrus, CK Valhall Tue/Thu, Morgonspins).
  - `docs/knee-rehab.md` — provisional generic patellofemoral template (activation/strength/cool-down pools, three weekly templates, what to ask the physio). Replace with Martin's actual prescription when available.
  - Google Calendar wired into `.mcp.json` (`@cocal/google-calendar-mcp`); `tools/auth_status.py` extended to report Calendar token state. `TM_CALENDAR_NAME` env var (Martin's calendar is `Training Mate`).
  - `journal/` scaffolded: `README.md`, `_template-plan.md`, `_template-log.md`.
  - `.claude/commands/plan-week.md`, `.claude/commands/log.md` — first two slash commands.
- **M1.75 — auth bring-up on Mac. DONE (2026-04-27).** All three providers green: `strava.ok=True`, `garmin.ok=True (format: modern)`, `google_calendar.ok=True`. Three commits on `main`:
  - `b11809a` — `tools/_common.py` reads camelCase keys from upstream `~/.config/strava-mcp/config.json`.
  - `33cbf4e` — Architecture audit: direnv adopted, Garmin MCP demoted, garth deprecation captured.
  - `1a321d0` — Garmin auth via `python-garminconnect>=0.3.3` modern format (single `garmin_tokens.json`); new `tools/garmin_auth_setup.py` for durable re-auth.

**Setup checklist for fresh clones (or new machines):**
1. **direnv** (one-time): `brew install direnv` + `echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc` + `direnv allow` in the repo. Repo's `.envrc` (committed) sources `.env`.
2. **OAuth credentials:**
   - `mv ~/Downloads/client_secret_*.json ~/.config/google-calendar-mcp/gcp-oauth.keys.json && chmod 600 …`
   - `cp .env.example .env`; fill in Strava + Garmin + Google credentials. `chmod 600 .env`.
3. **First-time Strava OAuth:** open `https://www.strava.com/oauth/authorize?client_id=$STRAVA_CLIENT_ID&response_type=code&redirect_uri=http%3A%2F%2Flocalhost&approval_prompt=force&scope=profile%3Aread_all%2Cactivity%3Aread_all%2Cactivity%3Aread%2Cprofile%3Awrite` in browser, copy `code` from redirect URL, exchange via curl + persist to `~/.config/strava-mcp/config.json` (camelCase keys: `clientId`, `clientSecret`, `accessToken`, `refreshToken`, `expiresAt`).
4. **First-time Google Calendar OAuth:** `npx -y @cocal/google-calendar-mcp auth`, complete browser dance.
5. **First-time Garmin auth:** `uv run python tools/garmin_auth_setup.py` (interactive — needs MFA in a real terminal).
6. **Verify:** `uv run python tools/auth_status.py` → all three `ok: true`.

- **M2 — Ingest + TSS. DONE (2026-04-27).** `analysis/tss.py` + `tools/sync_activities.py`/`list_activities.py`/`get_activity.py`/`estimate_ftp.py`. 22 TSS tests pass. Verified end-to-end against Martin's Strava (16 activities synced over 30 days; hrTSS computed correctly).
- **M3 — PMC + form. DONE.** `analysis/pmc.py` + `tools/compute_pmc.py`/`current_form.py` + `/form` skill. 16 PMC tests pass.
- **M4 — Wellness + daily surface. DONE.** `analysis/wellness.py` + `tools/daily_briefing.py` (extends `sync_activities.py` with `--include-wellness`). 15 wellness tests pass. Skills `/today`, `/sync`, `/log`.
- **M5 — Planner + Calendar read + coach subagent. DONE.** `analysis/workouts.py` + `tools/generate_workout.py`/`export_workout.py`/`plan_week.py`/`calendar_list.py`. First subagent `coach` (`.claude/agents/coach.md`). `/plan-week` skill rewritten to delegate to coach. Calendar read verified end-to-end. **`calendar_upsert_week.py` deferred** to a focused next session — risky write surface, deserves a dedicated diff-and-confirm pass.
- **M6 — KOM + wind. DONE.** `analysis/wind.py` + `tools/sync_segments.py`/`route_weather.py`/`kom_today.py`/`kom_threat.py`. Subagent `kom-hunter` + `/kom` skill. Open-Meteo verified end-to-end.
- **M7 — Fueling. DONE.** `analysis/fueling.py` + `tools/fuel_plan.py`. Subagent `fueling-advisor` + `/brief` skill.
- **M8 — Weekly review + polish. DONE.** `tools/weekly_review.py` + `tools/rate_limits.py`. Subagents `weekly-reviewer` (writes to `.claude/agent-memory/coach/MEMORY.md`) and `knee-rehab`. `/review` skill. Final docs/tools.md + CLAUDE.md doc index sweeps.

**Next session: real-world test run** of the coach agent. Suggested flow: `/sync` (pull latest activities + wellness) → `/today` (daily briefing) → `/plan-week` (let `coach` propose next week, review, optionally apply Calendar diff via the MCP server) → `/log` after each session through the week → `/review` Sunday evening. Tighten PLAN.md and CLAUDE.md based on what's confusing or wrong.

The deferred `calendar_upsert_week.py` is the obvious M9 candidate — needs a careful event-diff-and-confirm flow with idempotent IDs.

---

## Context

A personal AI trainer that plans, schedules, and tracks workouts (mostly cycling, some running, some strength), pulling activity data from Garmin and Strava, factoring weather/wind for KOM hunting, and grounding suggestions in actual training science (TSS / CTL / ATL / TSB, polarized/pyramidal distribution, fueling per kJ).

**Key architectural choice:** Claude Code itself *is* the trainer. There is no custom MCP server, no separate chat backend, no UI. We give Claude:
- a curated knowledge base (`docs/`) it reads on demand,
- a set of small Python CLI tools (`tools/`) it invokes via Bash and parses as JSON,
- specialized subagents (`.claude/agents/`) for narrow jobs (KOM ranking, weekly review, knee rehab),
- slash-command skills (`.claude/commands/`) for common workflows,
- a SQLite cache (`data/`) shared by all the tools,
- a `journal/` directory of weekly `.md` files Claude writes and updates — the rolling training diary, version-controlled,
- and a project `CLAUDE.md` pinning athlete profile + rules + an index of everything above.

**Two upstream MCP servers in `.mcp.json` autostart**, for ad-hoc API access only (not the primary surface):
- Strava: `@r-huijts/strava-mcp-server` (OAuth, read-only API). Resilient to empty env — falls back to `~/.config/strava-mcp/config.json`.
- Google Calendar: `@cocal/google-calendar-mcp` (Google Cloud OAuth, read + write events).

**Garmin MCP demoted** (`@nicolasvegam/garmin-connect-mcp`): kept installed for occasional ad-hoc questions but **not autostarted**, because (a) `garth` is deprecated, (b) it retry-loops with empty env and triggers Garmin's SSO 429 throttle. Primary Garmin access lives in `tools/*.py` via `python-garminconnect>=0.3.3` (post-garth, native SSO).

Local Python tools read the same on-disk token caches the MCP servers / direct libraries write (`~/.config/strava-mcp/config.json`, `~/.garmin-mcp/`, `~/.config/google-calendar-mcp/`) via `stravalib`, `python-garminconnect`, and `google-api-python-client` respectively. Direct lib calls (not MCP-to-MCP) because activity streams are big numeric arrays and routing them through MCP JSON would be wasteful.

## Architecture

```
Claude Code (the trainer)
  │
  ├── Reads on demand:
  │     CLAUDE.md                       athlete profile + rules + index
  │     docs/*.md                       training science, fueling, wind math, schema
  │
  ├── Invokes via Bash:
  │     tools/*.py                      small CLI scripts → JSON to stdout
  │       └── shared SQLite at data/training-mate.sqlite
  │
  ├── Delegates to subagents:
  │     .claude/agents/*.md             coach, kom-hunter, weekly-reviewer, fueling, knee-rehab
  │
  ├── User-triggered skills:
  │     .claude/commands/*.md           /plan-week, /today, /log, /kom, /brief, /sync, /review
  │
  ├── Writes diary:
  │     journal/YYYY-WW-{plan,log}.md   rolling training journal, committed to git
  │
  └── Three upstream MCP servers (loaded via .mcp.json) for ad-hoc API calls:
        strava-mcp        (npx)         OAuth + read-only Strava API
        garmin-mcp        (npx)         mobile SSO + read-only Garmin API
        google-calendar   (npx)         OAuth + read/write events
```

## Tool contract (shared across all `tools/*.py`)

- Single Python file, run as `uv run python tools/<name>.py [args...]`.
- Args via `argparse`; stdout is one JSON object; stderr is human-readable log lines.
- Exit 0 on success, non-zero with `{"error": "..."}` on failure.
- All DB access via `tools/_common.py:open_db()` (WAL, single connection per process).
- All Strava/Garmin auth via `tools/_common.py:strava_client()` / `garmin_client()` which read upstream MCP token caches.
- Rate-limit accounting persisted to `rate_limit_log` table.

## Core math (in `tools/`, documented in `docs/training-science.md` + `docs/wind-and-kom.md`)

**Power TSS (Coggan):**
```
NP   = (mean(rolling_mean(p, 30s)**4))**0.25
IF   = NP / FTP
TSS  = duration_h * IF**2 * 100
kJ   = sum(p)/1000
```

**hrTSS (TRIMP-based):**
```
hrr_i = (hr_i - rhr) / (max_hr - rhr)
trimp = sum( dt * hrr_i * 0.64 * exp(1.92 * hrr_i) )
hrTSS = trimp / trimp_at_threshold_for_1h * 100
```
Fallback when only avg HR known: `hrTSS = duration_h * (avg_hr/LTHR)**2 * 100`.

**rTSS:** Minetti grade-adjusted pace → `IF = NGS / threshold_pace`; `rTSS = duration_h * IF**2 * 100`.

**PMC (Banister exp-weighted, daily):**
```
CTL[d] = CTL[d-1] + (daily_tss[d] - CTL[d-1]) / 42
ATL[d] = ATL[d-1] + (daily_tss[d] - ATL[d-1]) / 7
TSB[d] = CTL[d-1] - ATL[d-1]
```
Backfill 6 months on seed. Recompute last 14 days on every ingest. Ramp target +3..+5 CTL/week; >+8 flags overreach.

**Wind/yaw (KOM ranking).** Open-Meteo gives "from" direction; convert to "to" bearing `W_to = (W_dir + 180) mod 360`.
```
delta = ((W_to - B_seg + 540) mod 360) - 180          # -180..+180
tail_kmh  = W_kmh * cos(radians(delta))
cross_kmh = W_kmh * sin(radians(delta))
score     = tail_kmh - 0.4*abs(cross_kmh) + (8<=temp<=18 ? +1 : 0) - (precip>0.5 ? 3 : 0)
```
Long curving segments: sample 20 polyline points and length-weight per-piece tail. Threat flag: `P_user(T_kom) ≥ 0.97 * kom_avg_w` AND `tail_kmh > 4`.

**Fueling:**
```
carbs_g_per_h      = clamp(60 + 30*IF, 60, 120)
pre_ride_carbs_g   = 1.5 * weight_kg
post_ride_carbs_g  = 1.0 * weight_kg
post_ride_protein  = 0.3 * weight_kg
fluids_ml_per_h    = 500 + 250*(temp_c>22)
sodium_mg_per_h    = 500..700 base, +300 if temp_c>25
```

## Sequencing (milestones)

1. **M1 — Skeleton. DONE.**
2. **M1.5 — Personal context + Calendar wiring. DONE.** (User setup steps still pending — see top of file.)
3. **M2 — Ingest + TSS.** `tools/sync_activities.py` (Strava + Garmin into SQLite), `tools/list_activities.py`, `tools/get_activity.py`, `analysis/tss.py` core, golden TSS test against a Golden Cheetah fixture FIT, `docs/training-science.md`.
4. **M3 — PMC + form.** `tools/compute_pmc.py`, `tools/current_form.py`. PMC self-check test (60 days of constant 50 TSS → CTL/ATL → 50, TSB → 0).
5. **M4 — Garmin wellness.** Extend `sync_activities.py` to pull HRV / body battery / readiness / sleep into `wellness_daily`. First version of `daily_briefing.py`.
6. **M5 — Planner + workout export + journal + calendar write.** `tools/generate_workout.py`, `tools/export_workout.py`, `tools/plan_week.py`, `tools/calendar_list.py`, `tools/calendar_upsert_week.py`, `docs/workout-library.md`. `/plan-week` writes `journal/YYYY-WW-plan.md` and offers a Calendar diff. `/log` and `/today` skills wired. Subagents `coach.md` + `knee-rehab.md`. Fill in `docs/knee-rehab.md` if Martin has a physio protocol by then.
7. **M6 — Segments + wind.** `tools/sync_segments.py`, `tools/kom_today.py`, `tools/kom_threat.py`, `docs/wind-and-kom.md`. Skill `/kom`, subagent `kom-hunter.md`.
8. **M7 — Routes + nutrition + briefing.** `tools/route_weather.py`, `tools/fuel_plan.py`, full `tools/daily_briefing.py`. Skill `/brief`, subagent `fueling-advisor.md`.
9. **M8 — Weekly review + polish.** `tools/weekly_review.py`, skill `/review` finalises `journal/YYYY-WW-log.md`, subagent `weekly-reviewer.md`. Rate-limit dashboard. CLAUDE.md doc pass.

## Risks & gotchas

- **MCP env propagation is non-magical.** Claude Code interpolates `${VAR}` in `.mcp.json` against its **launching shell's process env** at session start. `.env` is *not* auto-sourced. Without direnv (or manual `set -a; source .env; set +a; claude`), MCP servers spawn with empty env: Strava falls back to disk config (resilient), Calendar fails-fast (no tools registered), Garmin retry-loops password login and 429-throttles the user's IP. Direnv is the canonical fix — see Pending user setup. (Recorded in `~/.claude/projects/.../memory/feedback_mcp_env_propagation.md`.)
- **Strava 200/15min, 2000/day** — stream pulls dominate; persist `X-RateLimit-Usage` to `rate_limit_log`, throttle nightly sync, never re-pull a stream. Use `activity:read_all` scope for private rides.
- **Garmin ToS gray area** — keep ≤1 req/s; never automate workout push without explicit confirmation; `TM_GARMIN_DRYRUN=true` enforced in `tools/_common.py`.
- **`garth` is deprecated as of 2026-03-28** ([discussion #222](https://github.com/matin/garth/discussions/222)). The legacy garth-based login flow is broken for new logins. **Pin `python-garminconnect>=0.3.3`** — that release reimplements Garmin's mobile SSO directly using `curl_cffi` (Cloudflare TLS-fingerprint bypass) and no longer depends on garth. Existing OAuth1 tokens still work until expiry.
- **Garmin SSO 429 throttle** — triggered by repeated failed login attempts (e.g. retry-looping MCP server with empty creds). Clears in ~15-30 min, but compound failures extend it. Always kill all `garmin-connect-mcp` processes before retrying. Single-attempt logins with jittered backoff in `tools/garmin_*.py`.
- **Garmin token refresh (post-garth)** — `python-garminconnect` v0.3.3+ writes the same `~/.garmin-mcp/{oauth1_token,oauth2_token}.json` cache the upstream MCP reads. On 401, re-run the SSO flow with MFA prompt; surface as a structured stderr error.
- **NP for short rides** — flag `np_low_confidence=true` for activities <20 min.
- **Time zones** — store UTC; convert to local only for display and PMC daily roll-up.
- **Polyline precision** — Strava is precision 5 (`polyline.decode(s, 5)`).
- **Google OAuth in Testing mode** — refresh tokens expire after 7 days; re-run `npx -y @cocal/google-calendar-mcp auth` weekly. Verifying the OAuth client (privacy policy + demo video + ~3 days review) is high-cost-low-value for single-user; tolerate the weekly dance. Add a `tools/auth_status.py` warning at >5 days.
- **Calendar is a dedicated `Training Mate` calendar** — never write to other calendars.
- **Single-device assumption** — token caches live on Martin's laptop only. Phone/web sandbox sessions need a session-start hook + secret store; out of scope for now.
- **Don't commit secrets** — `.mcp.json` only references `${VAR}`; real values in `.env` (gitignored). `data/` gitignored. `.envrc` is committed because it just contains the `dotenv` directive.
- **Tool sprawl** — every new tool MUST be added to `docs/tools.md` with arg list and example JSON, or Claude won't know it exists.

## Out of scope for v1

- Push-to-watch / Garmin workout sync — risky write surface; emit `.zwo`/`.erg` files instead, sync manually.
- Web/mobile UI — Claude Code CLI is the trainer.
- Multi-user — auth and CTL state assume one athlete.
- Strava webhooks — would need a public endpoint; nightly polling is fine.
- ML form prediction — CTL/ATL is the standard model; ML adds nothing at this data scale.
- A custom training-mate MCP server — explicitly rejected; tools-as-CLI + docs is simpler.
- Cross-device session-start hook + secret store for tokens — punted to "when phone sessions become a real need".

## Resolved decisions

- Calendar event style: **one event per planned session** (not weekly summary).
- Calendar destination: **dedicated `Training Mate` calendar**.
- Knee rehab seed content: **generic patellofemoral template** (provisional, replace with physio protocol later).
- **Env loading: direnv with `.envrc` (committed, contains `dotenv`).** `.env` itself stays gitignored. Documented in Pending user setup.
- **MCP server roles** (post-2026-04-27 audit):
  - **Strava** (`@r-huijts/strava-mcp-server`): kept in `.mcp.json` autostart. Resilient — falls back to disk config if env empty. Used for ad-hoc queries (`/kom`, weekly review). Token cache `~/.config/strava-mcp/config.json` (camelCase keys: `clientId`, `accessToken`, `refreshToken`, `expiresAt`).
  - **Google Calendar** (`@cocal/google-calendar-mcp`): kept in `.mcp.json` autostart. Best-of-class community option (1.1k★). Token cache `~/.config/google-calendar-mcp/{tokens.json,gcp-oauth.keys.json}`.
  - **Garmin** (`@nicolasvegam/garmin-connect-mcp`): **demoted** — kept installed but not as primary surface. Use it for ad-hoc Garmin questions only. Primary access via `python-garminconnect>=0.3.3` directly (post-garth-removal). Shared token cache `~/.garmin-mcp/{oauth1_token,oauth2_token,profile}.json`.
- **Python library choices** for direct API access (CLI tools under `tools/`):
  - Strava: `stravalib` (mature, OAuth refresh built-in) reading the same `~/.config/strava-mcp/config.json` the MCP writes.
  - Garmin: `python-garminconnect>=0.3.3` (no garth dependency, native SSO via curl_cffi).
  - Calendar: `google-api-python-client` reading `~/.config/google-calendar-mcp/tokens.json`.
  - Weather: `httpx` directly to Open-Meteo (no MCP — too thin to wrap, free + keyless). Per `docs/wind-and-kom.md` for KOM yaw math.
- **No standalone weather MCP server.** Existing community options are tiny and abandoned; Open-Meteo's API is simple enough to wrap as `tools/route_weather.py`.
